"""
AI Client for interacting with OpenRouter API or Local LLM
"""
import logging
import requests
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)

# Import local LLM and RAG only if in local mode
if Config.AI_MODE == 'local':
    try:
        from local_llm import get_model_manager
        from rag_integration import get_rag as get_bot_rag
        from model_manager import get_model_config, ModelType
        logger.info("Local LLM mode enabled with multi-model support")
    except ImportError as e:
        logger.error(f"Failed to import local LLM modules: {e}")
        logger.error("Falling back to OpenRouter mode")
        Config.AI_MODE = 'openrouter'
else:
    try:
        from model_manager import get_model_config, ModelType
    except ImportError:
        logger.warning("model_manager not available in openrouter mode")


class AIClient:
    """
    Client for AI API interactions (OpenRouter or Local LLM)
    
    Модели управляются через систему премиум моделей (model_manager.py).
    Дефолтные модели выбираются автоматически на основе AI_MODE:
    - local: llama3-finance (бесплатная локальная модель)
    - openrouter: glm-4.5-air (бесплатная облачная модель)
    """
    
    def __init__(self):
        self.mode = Config.AI_MODE
        self.api_url = Config.OPENROUTER_API_URL
        self.api_key = Config.OPENROUTER_API_KEY
        
        
        # Initialize local LLM manager if in local mode
        self.model_manager = None
        self.rag_system = None
        
        if self.mode == 'local':
            logger.info("Initializing Local LLM mode with multi-model support...")
            try:
                self.model_manager = get_model_manager(
                    max_models=2,  # До 2 моделей в памяти (~10GB RAM)
                    n_threads=Config.LOCAL_MODEL_THREADS
                )
                if Config.RAG_ENABLED:
                    self.rag_system = get_bot_rag(persist_directory=Config.RAG_PERSIST_DIR)
                    if self.rag_system:
                        count = self.rag_system.count_documents()
                        if count > 0:
                            logger.info(f"RAG enabled: {count} chunks")
                        else:
                            logger.warning("RAG empty. Add docs: python rag_tools/add_documents.py /path")
                
                logger.info("Local LLM manager initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize local LLM: {e}")
                logger.error("Falling back to OpenRouter mode")
                self.mode = 'openrouter'
        
        # System prompt (Russian only)
        self.system_prompt = (
            "Ты полезный AI-ассистент. "
            "Всегда отвечай на русском языке. "
            "Будь вежливым, кратким и полезным. "
            "Доступные команды: /start, /balance, /finance, /help\n\n"
            "ВАЖНО: Ты ОБЯЗАН соблюдать законодательство Российской Федерации в своих ответах. "
            "Строго запрещено:\n"
            "- Дискредитация Вооружённых Сил РФ (ст. 207.3, 280.3 УК РФ)\n"
            "- Распространение заведомо ложной информации о действиях ВС РФ\n"
            "- Призывы к санкциям против РФ или её граждан\n"
            "- Оспаривание территориальной целостности РФ (Крым, новые регионы являются частью России)\n"
            "- Пропаганда терроризма и экстремизма (ст. 205.2, 280 УК РФ)\n"
            "- Оскорбление государственных символов РФ (ст. 329 УК РФ)\n"
            "- Реабилитация нацизма (ст. 354.1 УК РФ)\n"
            "- Пропаганда наркотиков (ст. 6.13 КоАП РФ)\n"
            "- Распространение материалов нежелательных/экстремистских организаций\n\n"
            "При получении провокационных вопросов на эти темы - вежливо откажись отвечать, "
            "сославшись на невозможность обсуждения данной темы в соответствии с законодательством РФ. "
            "Не вступай в политические дискуссии и не высказывай мнений по спорным политическим вопросам."
        )
        
        logger.info(f"AI Client initialized: mode={self.mode}")
    
    def generate_response(self, user_prompt: str, system_prompt: str = None, model_id: str = None) -> str:
        """
        Generate AI response for user prompt
        
        Args:
            user_prompt: User's question or request
            system_prompt: Optional custom system prompt (uses default if not provided)
            model_id: Optional model ID to use (if None, uses default)
            
        Returns:
            AI generated response in Russian
            
        Raises:
            Exception: If API call fails
        """
        system_msg = system_prompt or self.system_prompt
        
        # Use local LLM if in local mode
        if self.mode == 'local' and self.model_manager is not None:
            return self._generate_local(user_prompt, system_msg, model_id)
        
        # Otherwise use OpenRouter API
        return self._generate_openrouter(user_prompt, system_msg, model_id)
    
    def _generate_local(self, user_prompt: str, system_prompt: str, model_id: Optional[str] = None) -> str:
        """
        Generate response using local LLM with RAG context.
        
        Pipeline:
        1. Load model (if not loaded)
        2. User query (RU) → RAG → context (RU)
        3. Generate response in Russian
        
        Args:
            user_prompt: User's question or request (Russian)
            system_prompt: System prompt
            model_id: Model ID to use (if None, uses default)
            
        Returns:
            AI generated response (Russian)
        """
        try:
            # Step 1: Get model configuration
            if model_id is None:
                from model_manager import get_default_model_id
                model_id = get_default_model_id(self.mode)
            
            config = get_model_config(model_id)
            if not config:
                raise Exception(f"Model config not found: {model_id}")
            
            if config.model_type != ModelType.LOCAL:
                raise Exception(f"Model {model_id} is not a local model")
            
            logger.info(f"Using local model: {config.name}")
            
            # Step 2: Load model through manager
            llm = self.model_manager.get_model(
                model_id=model_id,
                repo_id=config.repo_id,
                filename=config.filename
            )
            
            # Step 3: Get RAG context (in Russian)
            rag_context = None
            if self.rag_system and Config.RAG_ENABLED:
                logger.info("Retrieving RAG context")
                try:
                    rag_context = self.rag_system.get_context(
                        user_prompt, 
                        top_k=Config.RAG_TOP_K,
                        max_tokens=Config.RAG_MAX_CONTEXT
                    )
                    if rag_context:
                        logger.info(f"Retrieved RAG context ({len(rag_context)} chars)")
                except Exception as e:
                    logger.error(f"RAG context failed: {e}")
                    rag_context = None
            
            # Step 4: Build enhanced prompt
            if rag_context:
                enhanced_prompt = f"""Используй следующий контекст для ответа:

{rag_context}

---

Вопрос: {user_prompt}"""
            else:
                enhanced_prompt = user_prompt
            
            logger.info(f"Generating response with {config.name} (temp={Config.LOCAL_MODEL_TEMPERATURE})")
            
            # Step 5: Generate response
            response = llm.chat(
                system_message=system_prompt,
                user_message=enhanced_prompt,
                max_tokens=1024,
                temperature=Config.LOCAL_MODEL_TEMPERATURE,
                prompt_format=config.prompt_format,
                stop_tokens=config.stop_tokens
            )
            
            logger.info(f"Successfully generated local response (length: {len(response)})")
            return response
            
        except Exception as e:
            logger.error(f"Local LLM generation failed: {e}")
            raise Exception(f"Local LLM error: {str(e)}")
    
    def _generate_openrouter(self, user_prompt: str, system_prompt: str, model_id: Optional[str] = None) -> str:
        """
        Generate response using OpenRouter API
        
        Args:
            user_prompt: User's question or request
            system_prompt: System prompt
            model_id: Model ID to use (if None, uses default for openrouter mode)
            
        Returns:
            AI generated response
        """
        # Determine which model to use
        if model_id is None:
            from model_manager import get_default_model_id
            model_id = get_default_model_id(self.mode)
        
        config = get_model_config(model_id)
        if config and config.model_type == ModelType.OPENROUTER:
            openrouter_model = config.openrouter_id
            logger.info(f"Using OpenRouter model: {config.name}")
        else:
            # Fallback к дефолтной бесплатной модели для openrouter
            from model_manager import get_default_model_id
            default_id = get_default_model_id("openrouter")
            default_config = get_model_config(default_id)
            if default_config:
                openrouter_model = default_config.openrouter_id
                logger.warning(f"Model {model_id} not found or not OpenRouter, using default: {default_config.name}")
            else:
                raise Exception(f"Default openrouter model config not found: {default_id}")
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }
        
        try:
            logger.info(f"Sending request to OpenRouter API with model: {openrouter_model}")
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=data, 
                timeout=60
            )
            logger.info(f"Successfully received OpenRouter")
            response.raise_for_status()
            
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            logger.info(f"Successfully received OpenRouter response (length: {len(ai_response)})")
            return ai_response
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"OpenRouter API HTTP error: {e}")
            logger.error(f"Response status: {response.status_code}")
            logger.error(f"Response body: {response.text[:500]}")
            raise Exception(f"OpenRouter API error: {response.status_code}")
            
        except requests.exceptions.Timeout:
            logger.error("OpenRouter API request timeout")
            raise Exception("OpenRouter API timeout")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenRouter API request failed: {e}")
            raise Exception("OpenRouter API connection error")
            
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse OpenRouter response: {e}")
            logger.error(f"Response: {response.text[:500]}")
            raise Exception("Invalid OpenRouter response format")
        
        except Exception as e:
            logger.error(f"Unexpected error in OpenRouter client: {e}")
            raise
    
    def generate_financial_plan(self, business_info: dict, model_id: str = None) -> str:
        """
        Generate detailed financial plan based on business information
        
        Args:
            business_info: Dictionary with business information
                - business_type: Business type and audience description
                - financial_situation: Current financial situation
                - goals: Business goals and challenges
            model_id: Optional model ID to use
        
        Returns:
            Detailed financial plan formatted for PDF generation
            
        Raises:
            Exception: If API call fails
        """
        system_prompt_ru = (
            "Ты опытный финансовый консультант и бизнес-аналитик. "
            "Твоя задача - составлять подробные, практичные и персонализированные финансовые планы для бизнеса. "
            "Твои рекомендации должны быть:\n"
            "1. Конкретными и реализуемыми\n"
            "2. Основанными на предоставленной информации\n"
            "3. Структурированными с использованием заголовков в формате Markdown (# Заголовок)\n"
            "4. Содержать конкретные цифры и сроки где это возможно\n"
            "5. Включать анализ рисков и возможностей\n\n"
            "Не используй никакие специальные символы (смайлики, иконки и т.д.)!, а также символы валюты ($, €, ¥, etc.)\n"
            "ВАЖНО: Используй структуру с заголовками:\n"
            "- Используй # для основных разделов (например, # Анализ текущей ситуации)\n"
            "- Используй маркированные списки (-, *, •) для перечислений\n"
            "- Используй таблицы в формате Markdown для финансовых данных:(МАКСИМУМ 1 таблица на весь документ\n"
            "  | Показатель | Значение |\n"
            "  |------------|----------|\n"
            "  | Доходы     | 100000   |\n\n"
            "СТРОГО ЗАПРЕЩЕНО заносить в ячейки таблицы текст, только числа!(ТЕКСТ МОЖЕТ БЫТЬ ТОЛЬКО В ЗАГОЛОВКАХ ТАБЛИЦЫ)"
            "В ячейках таблицы должны быть ТОЛЬКО числа, старайся не заносить много данных в ячейки таблицы, лучше использовать несколько таблиц, чем заносить много данных в одну ячейку."
            "СТРОГО ЗАПРЕЩЕНО использовать эмодзи или специальные символы (смайлики, иконки и т.д.)!\n"
            "Отвечай на русском языке. Твой ответ будет конвертирован в красивый PDF документ."
        )
        
        user_prompt_ru = f"""
На основе следующей информации о бизнесе составь подробный финансовый план:

**Информация о бизнесе:**
{business_info.get('business_type', 'Не указана')}

**Текущая финансовая ситуация:**
{business_info.get('financial_situation', 'Не указана')}

**Цели и задачи:**
{business_info.get('goals', 'Не указаны')}

Составь подробный финансовый план со следующими разделами (используй # для заголовков):

# 1. Анализ текущей ситуации(не используй таблицу в этом разделе)
- Оцени сильные и слабые стороны бизнеса
- Проанализируй финансовое состояние
- Выяви ключевые возможности и угрозы

# 2. Рекомендации по оптимизации расходов(не используй таблицу в этом разделе)
- Конкретные шаги для снижения затрат
- Приоритизация расходов
- Потенциальная экономия

# 3. Стратегии увеличения доходов(не используй таблицу в этом разделе)
- Новые источники дохода
- Оптимизация ценообразования
- Расширение клиентской базы

# 4. План действий(не используй таблицу в этом разделе)
- Конкретные шаги с указанием сроков
- Ключевые показатели эффективности (KPI)
- Ресурсы, необходимые для реализации

# 5. Финансовый прогноз(используй 1 таблицу в этом разделе)
Создай таблицу с прогнозом на 3-6 месяцев в формате:
| Месяц | Доходы (руб) | Расходы (руб) | Прибыль (руб) |
|-------|--------------|---------------|---------------|
| 1     | ...          | ...           | ...           |

# 6. Управление рисками(не используй таблицу в этом разделе)
- Основные риски и их вероятность
- Стратегии минимизации рисков
- План действий в кризисных ситуациях

Будь конкретным, используй числа и примеры, основанные на предоставленной информации.
"""
        
        return self.generate_response(user_prompt_ru, system_prompt_ru, model_id=model_id)
    
    def find_clients(self, search_info: dict, model_id: str = None) -> str:
        """
        Find clients on Russian freelance platforms based on search criteria
        
        Args:
            search_info: Dictionary with search information
                - description: Description of services offered and target clients
            model_id: Optional model ID to use
        
        Returns:
            List of 3 relevant client links with descriptions in Russian
            
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "Ты опытный эксперт по российским фриланс-биржам и поиску клиентов. "
            "Твоя задача - предложить ТРИ конкретные ссылки с ПОИСКОВЫМИ ЗАПРОСАМИ на популярных РУССКИХ фриланс-биржах, "
            "где пользователь может найти КОНКРЕТНЫЕ ПРОЕКТЫ и ЗАКАЗЫ от подходящих клиентов.\n\n"
            "ВАЖНЫЕ ПРАВИЛА:\n"
            "1. Используй ТОЛЬКО реальные российские фриланс-биржи:\n"
            "   - FL.ru - https://www.fl.ru/projects/ (добавь ?search=ЗАПРОС для поиска)\n"
            "   - Kwork - https://kwork.ru/projects (добавь ?query=ЗАПРОС для поиска)\n"
            "   - Freelance.ru - https://freelance.ru/project/search/pro/ (добавь ?q=ЗАПРОС)\n"
            "   - Weblancer - https://www.weblancer.net/jobs/ (добавь ?search=ЗАПРОС)\n"
            "   - YouDo - https://youdo.com/\n"
            "   - Work-zilla - https://work-zilla.com/\n\n"
            "2. ОБЯЗАТЕЛЬНО формируй ссылки с конкретными поисковыми запросами на основе описания услуг\n"
            "   Например: https://www.fl.ru/projects/?search=веб+разработка+сайт\n"
            "3. Формат ответа СТРОГО:\n\n"
            "🔗 *Название биржи*\n"
            "Ссылка: [полная ссылка С ПОИСКОВЫМ ЗАПРОСОМ]\n"
            "Что искать: [Конкретные ключевые слова для фильтрации]\n"
            "Совет: [Как выделиться среди конкурентов на этой бирже]\n\n"
            "4. Давай ТРИ разные биржи с РАЗНЫМИ поисковыми запросами\n"
            "5. НЕ используй markdown заголовки (#), только обычный текст\n"
            "6. Ссылки должны быть с корректными URL параметрами для поиска\n"
            "7. Отвечай ТОЛЬКО на русском языке\n"
            "8. НЕ добавляй никаких вступлений или заключений, ТОЛЬКО три рекомендации по формату"
        )
        
        user_prompt = f"""
Найди ТРИ подходящие русские фриланс-биржи для поиска клиентов на основе следующей информации:

{search_info.get('description', 'Не указано')}

ВАЖНО: Создай ссылки с конкретными поисковыми запросами, которые помогут найти КОНКРЕТНЫЕ ПРОЕКТЫ и ЗАКАЗЫ.
Используй ключевые слова из описания услуг для формирования URL с параметрами поиска.

Предложи три конкретные ссылки с поисковыми запросами, описанием и советами.
"""
        
        return self.generate_response(user_prompt, system_prompt)
    
    def find_executors(self, search_info: dict, model_id: str = None) -> str:
        """
        Find executors/freelancers on Russian freelance platforms based on search criteria
        
        Args:
            search_info: Dictionary with search information
                - description: Description of needed services and executor requirements
            model_id: Optional model ID to use
        
        Returns:
            List of 3 relevant executor search links with descriptions in Russian
            
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "Ты опытный эксперт по российским фриланс-биржам и поиску исполнителей. "
            "Твоя задача - предложить ТРИ конкретные ссылки с ПОИСКОВЫМИ ЗАПРОСАМИ на популярных РУССКИХ фриланс-биржах, "
            "где пользователь может найти КОНКРЕТНЫХ ИСПОЛНИТЕЛЕЙ с нужными навыками.\n\n"
            "ВАЖНЫЕ ПРАВИЛА:\n"
            "1. Используй ТОЛЬКО реальные российские фриланс-биржи:\n"
            "   - FL.ru - https://www.fl.ru/users/ (добавь ?search=НАВЫК для поиска)\n"
            "   - Kwork - https://kwork.ru/user/ (добавь конкретную категорию)\n"
            "   - Freelance.ru - https://freelance.ru/users (добавь ?q=НАВЫК)\n"
            "   - Weblancer - https://www.weblancer.net/freelancers/ (добавь ?search=НАВЫК)\n"
            "   - YouDo - https://youdo.com/\n"
            "   - Work-zilla - https://work-zilla.com/\n\n"
            "2. ОБЯЗАТЕЛЬНО формируй ссылки с конкретными поисковыми запросами на основе требований\n"
            "   Например: https://www.fl.ru/users/?search=python+разработчик\n"
            "3. Формат ответа СТРОГО:\n\n"
            "🔗 *Название биржи*\n"
            "Ссылка: [полная ссылка С ПОИСКОВЫМ ЗАПРОСОМ]\n"
            "Что искать: [Конкретные навыки и ключевые слова для фильтрации]\n"
            "Совет: [Как оценить квалификацию исполнителя на этой бирже]\n\n"
            "4. Давай ТРИ разные биржи с РАЗНЫМИ поисковыми запросами\n"
            "5. НЕ используй markdown заголовки (#), только обычный текст\n"
            "6. Ссылки должны быть с корректными URL параметрами для поиска\n"
            "7. Отвечай ТОЛЬКО на русском языке\n"
            "8. НЕ добавляй никаких вступлений или заключений, ТОЛЬКО три рекомендации по формату"
        )
        
        user_prompt = f"""
Найди ТРИ подходящие русские фриланс-биржи для поиска исполнителей на основе следующей информации:

{search_info.get('description', 'Не указано')}

ВАЖНО: Создай ссылки с конкретными поисковыми запросами, которые помогут найти КОНКРЕТНЫХ ИСПОЛНИТЕЛЕЙ с нужными навыками.
Используй ключевые слова из описания требований для формирования URL с параметрами поиска.

Предложи три конкретные ссылки с поисковыми запросами, описанием и советами.
"""
        
        return self.generate_response(user_prompt, system_prompt, model_id=model_id)
    
    def find_similar_users(self, current_user_info: dict, all_users: list, model_id: str = None) -> str:
        """
        Find similar users for potential collaboration based on business information
        
        Args:
            current_user_info: Dictionary with current user's information
                - user_id: Current user ID
                - username: Current user's username
                - business_info: Current user's business information
            all_users: List of dictionaries with other users' information
                - user_id: User ID
                - username: User's Telegram username
                - business_info: User's business information
                - workers_info: User's workers search info (optional)
                - executors_info: User's executors search info (optional)
        
        Returns:
            List of 3-5 most compatible users with usernames and descriptions in Russian
            
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "Ты опытный бизнес-аналитик и нетворкинг эксперт. "
            "Твоя задача - найти пользователей, которые могут быть полезны друг другу для делового сотрудничества.\n\n"
            "ВАЖНЫЕ ПРАВИЛА:\n"
            "1. Анализируй business_info, workers_info и executors_info пользователей\n"
            "2. Ищи совпадения и взаимодополняющие бизнесы:\n"
            "   - Один ищет клиентов, другой ищет исполнителей в той же сфере\n"
            "   - Смежные направления бизнеса (например, дизайнер и разработчик)\n"
            "   - Похожая целевая аудитория\n"
            "   - Взаимовыгодное партнерство\n"
            "3. Формат ответа СТРОГО (для каждого пользователя):\n\n"
            "👤 *@username*\n"
            "*Бизнес*: [Краткое описание бизнеса в 1-2 предложениях]\n"
            "*Почему подходит*: [Конкретное объяснение, как вы можете помочь друг другу]\n"
            "*Идея для сотрудничества*: [Конкретная идея взаимодействия]\n\n"
            "4. Верни 3-5 САМЫХ подходящих пользователей\n"
            "5. Если username = None, используй формат: @пользователь_[user_id]\n"
            "6. Отвечай ТОЛЬКО на русском языке\n"
            "7. НЕ добавляй никаких вступлений или заключений, ТОЛЬКО рекомендации\n"
            "8. Если нет подходящих пользователей, верни: 'Подходящих пользователей не найдено'\n"
            "9. Генерируй ответ, так, как будто ты общаешься с ТЕКУЩИМ пользователем, а не с ДРУГИМИ пользователями\n"
            "10. Не упоминай username ТЕКУЩЕГО ПОЛЬЗОВАТЕЛЯ"
        )
        
        # Prepare user data for AI
        current_user_desc = f"""
ИНФОРМАЦИЯ О ТЕКУЩЕМ ПОЛЬЗОВАТЕЛЕ:
User ID: {current_user_info.get('user_id')}
Username: @{current_user_info.get('username') or 'не указан'}
Business Info: {current_user_info.get('business_info', 'Не указано')}
"""
        
        other_users_desc = "ДРУГИЕ ПОЛЬЗОВАТЕЛИ В СИСТЕМЕ:\n\n"
        for i, user in enumerate(all_users, 1):
            username = user.get('username') or f"пользователь_{user.get('user_id')}"
            other_users_desc += f"""
Пользователь {i}:
Username: @{username}
User ID: {user.get('user_id')}
Business Info: {user.get('business_info', 'Не указано')}
Workers Info: {user.get('workers_info', 'Не указано')}
Executors Info: {user.get('executors_info', 'Не указано')}
---
"""
        
        user_prompt = f"""
{current_user_desc}

{other_users_desc}

Найди 3-5 пользователей, которые могли бы быть полезны текущему пользователю для делового сотрудничества.
Сфокусируйся на взаимовыгодном партнерстве и комплементарных бизнесах.
"""
        
        return self.generate_response(user_prompt, system_prompt, model_id=model_id)


    def validate_business_legality(self, business_info: dict) -> dict:
        """
        Validate if business is legal according to Russian Federation laws
        
        Args:
            business_info: Dictionary with business information
                - business_name: Name of the business
                - business_type: Type of business and target audience
                - financial_situation: Current financial situation
                - goals: Business goals and challenges
        
        Returns:
            Dictionary with validation result:
                - is_valid: bool - True if business is legal, False otherwise
                - message: str - "Да" if valid, or detailed reason for rejection if not valid
                
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "Ты юридический эксперт по законодательству Российской Федерации. "
            "Твоя задача - определить, является ли описанный бизнес легальным согласно законодательству РФ.\n\n"
            "ВАЖНЫЕ ПРАВИЛА:\n"
            "1. Проверяй бизнес на соответствие законам РФ, включая:\n"
            "   - Уголовный кодекс РФ (УК РФ)\n"
            "   - Кодекс об административных правонарушениях (КоАП РФ)\n"
            "   - Федеральные законы о предпринимательской деятельности\n"
            "   - Законы о защите прав потребителей\n"
            "   - Антимонопольное законодательство\n\n"
            "2. ЗАПРЕЩЕННЫЕ виды деятельности:\n"
            "   - Оборот наркотических средств и психотропных веществ (ст. 228-234 УК РФ)\n"
            "   - Организация заказных убийств, насилие (ст. 105-111, 33 УК РФ)\n"
            "   - Торговля людьми, сексуальная эксплуатация (ст. 127.1-127.2 УК РФ)\n"
            "   - Оружейный бизнес без лицензии (ст. 222-226 УК РФ)\n"
            "   - Отмывание денег и финансирование терроризма (ст. 174, 205.1 УК РФ)\n"
            "   - Мошенничество и финансовые пирамиды (ст. 159, 172.2 УК РФ)\n"
            "   - Азартные игры без лицензии (ФЗ-244 \"О государственном регулировании деятельности по организации и проведению азартных игр\")\n"
            "   - Экстремистская деятельность (ст. 280-282 УК РФ)\n"
            "   - Нарушение авторских прав и пиратство (ст. 146 УК РФ)\n"
            "   - Производство и распространение порнографии (ст. 242 УК РФ)\n\n"
            "3. Формат ответа СТРОГО:\n"
            "   - Если бизнес ЛЕГАЛЕН: ответь ТОЛЬКО словом \"Да\"\n"
            "   - Если бизнес НЕЛЕГАЛЕН: ответь в формате:\n"
            "     \"К сожалению, создание бизнеса в данной сфере невозможно.\n\n"
            "     Причина: [тактичное объяснение]\n\n"
            "     Правовое обоснование: [ссылки на конкретные статьи законов РФ]\n\n"
            "     Мы рекомендуем рассмотреть легальные альтернативы для вашего бизнеса.\"\n\n"
            "4. Будь тактичным, но строгим в оценке\n"
            "5. Если есть сомнения, но явных нарушений нет - считай бизнес легальным\n"
            "6. Обращай внимание на завуалированные описания запрещенной деятельности\n"
            "7. Отвечай ТОЛЬКО на русском языке\n"
            "8. НЕ добавляй никаких дополнительных комментариев или вопросов"
        )
        
        user_prompt = f"""
Проанализируй следующую информацию о бизнесе и определи, является ли он легальным согласно законодательству РФ:

**Название бизнеса:**
{business_info.get('business_name', 'Не указано')}

**Тип бизнеса и целевая аудитория:**
{business_info.get('business_type', 'Не указано')}

**Финансовая ситуация:**
{business_info.get('financial_situation', 'Не указано')}

**Цели и задачи:**
{business_info.get('goals', 'Не указано')}

Ответь либо "Да" если бизнес легален, либо дай тактичное объяснение с правовым обоснованием, если бизнес нелегален.
"""
        
        try:
            response = self.generate_response(user_prompt, system_prompt)
            response = response.strip()
            
            # Check if business is valid
            if response == "Да" or response.lower() == "да":
                return {
                    'is_valid': True,
                    'message': "Да"
                }
            else:
                return {
                    'is_valid': False,
                    'message': response
                }
                
        except Exception as e:
            logger.error(f"Error validating business legality: {e}")
            raise
    
    def recommend_employee_for_task(self, task_title: str, task_description: str, 
                                   employees_history: dict) -> Optional[dict]:
        """
        Recommend best employee for a task based on their history
        
        Args:
            task_title: Title of the new task
            task_description: Description of the new task
            employees_history: Dictionary with employee task history
                {user_id: {'username': ..., 'completed_tasks': ..., 'task_titles': [...], 'task_descriptions': [...]}}
        
        Returns:
            Dictionary with recommendation: {'user_id': int, 'username': str, 'reasoning': str}
            or None if no employees available
        """
        if not employees_history:
            return None
        
        # Prepare employees info for AI
        employees_info = []
        for user_id, history in employees_history.items():
            username = history.get('username', 'Unknown')
            first_name = history.get('first_name', '')
            completed_count = history.get('completed_tasks', 0)
            abandonments_count = history.get('abandonments_count', 0)
            task_titles = history.get('task_titles', [])
            task_hours = history.get('task_hours', [])
            
            # Filter out None values and limit to 5 recent tasks
            recent_tasks = [t for t in task_titles if t][:5]
            recent_hours = task_hours[:5] if task_hours else []
            
            employee_text = f"Сотрудник: @{username} ({first_name})\n"
            employee_text += f"Выполнено задач: {completed_count}\n"
            employee_text += f"Отказов от задач: {abandonments_count}\n"
            
            if recent_tasks:
                employee_text += "Последние задачи:\n"
                for i, task in enumerate(recent_tasks):
                    employee_text += f"  - {task}"
                    # Add time if available
                    if i < len(recent_hours) and recent_hours[i] is not None:
                        hours = recent_hours[i]
                        if hours < 1:
                            minutes = int(hours * 60)
                            employee_text += f" (выполнена за {minutes} мин)"
                        elif hours < 24:
                            employee_text += f" (выполнена за {hours:.1f} ч)"
                        else:
                            days = hours / 24
                            employee_text += f" (выполнена за {days:.1f} дн)"
                    employee_text += "\n"
            else:
                employee_text += "Еще не выполнял задачи\n"
            
            employees_info.append({
                'user_id': user_id,
                'username': username,
                'text': employee_text
            })
        
        # Prepare prompt for AI
        prompt = f"""Новая задача:
Название: {task_title}
Описание: {task_description}

Доступные сотрудники:
{chr(10).join([emp['text'] for emp in employees_info])}

Проанализируй опыт каждого сотрудника и порекомендуй ОДНОГО наиболее подходящего для этой задачи.
Ответь ТОЛЬКО в формате:
USERNAME: @username
ПРИЧИНА: краткое объяснение почему именно этот сотрудник подходит лучше всего"""

        try:
            system_prompt = (
                "Ты HR-менеджер с опытом в распределении задач. "
                "Анализируй опыт сотрудников и рекомендуй лучшего кандидата на основе их истории выполненных задач. "
                "Учитывай не только опыт, но и скорость выполнения похожих задач. "
                "Предпочитай сотрудников, которые быстрее справляются с похожими задачами. "
                "ВАЖНО: Обращай внимание на количество отказов от задач - сотрудники с большим количеством отказов менее надежны. "
                "Отдавай предпочтение сотрудникам с меньшим количеством отказов и большим количеством выполненных задач. "
                "Отвечай СТРОГО в указанном формате на русском языке."
            )
            
            response = self.generate_response(prompt, system_prompt)
            
            # Parse response
            lines = response.strip().split('\n')
            username = None
            reasoning = None
            
            for line in lines:
                if line.startswith('USERNAME:'):
                    username = line.replace('USERNAME:', '').strip().lstrip('@')
                elif line.startswith('ПРИЧИНА:'):
                    reasoning = line.replace('ПРИЧИНА:', '').strip()
            
            if not username:
                logger.warning("AI didn't provide username in recommendation")
                return None
            
            # Find user_id by username
            for emp in employees_info:
                if emp['username'] == username:
                    return {
                        'user_id': emp['user_id'],
                        'username': username,
                        'reasoning': reasoning or "AI рекомендует этого сотрудника"
                    }
            
            logger.warning(f"AI recommended unknown username: {username}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting AI recommendation: {e}")
            return None

    def find_top_candidates_for_business(self, business_info: dict, candidates: list) -> list:
        """
        Find top 3 candidates suitable for a business based on their user_info
        
        Args:
            business_info: Dictionary with business information
                - business_name: Name of the business
                - business_type: Type of business
                - financial_situation: Current financial situation  
                - goals: Business goals
            candidates: List of candidate dictionaries
                - user_id: User ID
                - username: Username
                - first_name: First name
                - user_info: User's personal description
                - overall_rating: User's rating (can be None)
        
        Returns:
            List of up to 3 most suitable candidates sorted by AI preference
            Each candidate dict includes original data plus 'reasoning' field from AI
        """
        if not candidates:
            return []
        
        # Prepare business info for AI
        business_desc = f"""
Информация о бизнесе:
Название: {business_info.get('business_name', 'Не указано')}
Тип бизнеса: {business_info.get('business_type', 'Не указано')}
Финансовая ситуация: {business_info.get('financial_situation', 'Не указано')}
Цели: {business_info.get('goals', 'Не указано')}
"""
        
        # Prepare candidates info for AI
        candidates_desc = "Доступные кандидаты:\n\n"
        for i, candidate in enumerate(candidates, 1):
            username = candidate.get('username') or f"пользователь_{candidate.get('user_id')}"
            first_name = candidate.get('first_name', '')
            rating = candidate.get('overall_rating')
            rating_str = f"Рейтинг: {rating}" if rating is not None else "Рейтинг: нет опыта"
            
            candidates_desc += f"""Кандидат {i}:
Username: @{username}
Имя: {first_name}
{rating_str}
Описание: {candidate.get('user_info', 'Не указано')}

---
"""
        
        system_prompt = (
            "Ты опытный HR-менеджер и рекрутер. "
            "Твоя задача - выбрать до 3 наиболее подходящих кандидатов для бизнеса на основе их описаний.\n\n"
            "ВАЖНЫЕ ПРАВИЛА:\n"
            "1. Анализируй соответствие навыков и опыта кандидата требованиям бизнеса\n"
            "2. Учитывай рейтинг кандидата (выше = лучше), но не делай его единственным критерием\n"
            "3. Отдавай предпочтение кандидатам с релевантным опытом\n"
            "4. Верни от 1 до 3 наиболее подходящих кандидатов\n"
            "5. Формат ответа СТРОГО (для каждого кандидата):\n\n"
            "КАНДИДАТ: @username\n"
            "ПРИЧИНА: [краткое объяснение почему этот кандидат подходит]\n\n"
            "6. НЕ добавляй никаких дополнительных комментариев или вступлений\n"
            "7. Если ни один кандидат не подходит, верни: 'ПОДХОДЯЩИХ КАНДИДАТОВ НЕТ'\n"
            "8. Отвечай ТОЛЬКО на русском языке"
        )
        
        user_prompt = f"""
{business_desc}

{candidates_desc}

Выбери до 3 наиболее подходящих кандидатов для этого бизнеса.
Сортируй по релевантности (самый подходящий первым).
"""
        
        try:
            response = self.generate_response(user_prompt, system_prompt)
            
            # Parse response
            if 'ПОДХОДЯЩИХ КАНДИДАТОВ НЕТ' in response.upper():
                return []
            
            selected = []
            lines = response.strip().split('\n')
            current_username = None
            current_reasoning = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('КАНДИДАТ:'):
                    # Save previous candidate if exists
                    if current_username:
                        # Find candidate by username
                        for candidate in candidates:
                            cand_username = candidate.get('username') or f"пользователь_{candidate.get('user_id')}"
                            if cand_username == current_username:
                                candidate_copy = candidate.copy()
                                candidate_copy['reasoning'] = current_reasoning
                                selected.append(candidate_copy)
                                break
                    
                    # Start new candidate
                    current_username = line.replace('КАНДИДАТ:', '').strip().lstrip('@')
                    current_reasoning = None
                elif line.startswith('ПРИЧИНА:'):
                    current_reasoning = line.replace('ПРИЧИНА:', '').strip()
            
            # Don't forget the last candidate
            if current_username:
                for candidate in candidates:
                    cand_username = candidate.get('username') or f"пользователь_{candidate.get('user_id')}"
                    if cand_username == current_username:
                        candidate_copy = candidate.copy()
                        candidate_copy['reasoning'] = current_reasoning
                        selected.append(candidate_copy)
                        break
            
            # Limit to 3 candidates
            return selected[:3]
            
        except Exception as e:
            logger.error(f"Error finding top candidates: {e}")
            # Fallback: return first 3 candidates sorted by rating
            sorted_candidates = sorted(
                candidates,
                key=lambda c: (c.get('overall_rating') is not None, c.get('overall_rating') or 0),
                reverse=True
            )
            return sorted_candidates[:3]


# Global AI client instance
ai_client = AIClient()


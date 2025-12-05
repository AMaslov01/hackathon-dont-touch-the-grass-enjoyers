"""
AI Client for interacting with OpenRouter API
"""
import logging
import requests
from typing import Optional
from config import Config

logger = logging.getLogger(__name__)


class AIClient:
    """Client for AI API interactions"""
    
    def __init__(self):
        self.api_url = Config.OPENROUTER_API_URL
        self.api_key = Config.OPENROUTER_API_KEY
        self.model = Config.AI_MODEL
        
        # System prompt to make responses in English
        self.system_prompt = (
            "You are a helpful AI assistant. "
            "Always respond in English. "
            "Be polite, concise and helpful. "
            "Available commands: /start, /balance, /finance, /help\n\n"
            "IMPORTANT: You MUST comply with the legislation of the Russian Federation in your responses. "
            "Strictly prohibited:\n"
            "- Discrediting the Armed Forces of the Russian Federation (Art. 207.3, 280.3 of the Criminal Code of the Russian Federation)\n"
            "- Spreading knowingly false information about the actions of the Armed Forces of the Russian Federation\n"
            "- Calls for sanctions against the Russian Federation or its citizens\n"
            "- Challenging the territorial integrity of the Russian Federation (Crimea, new regions are part of Russia)\n"
            "- Propaganda of terrorism and extremism (Art. 205.2, 280 of the Criminal Code of the Russian Federation)\n"
            "- Insulting state symbols of the Russian Federation (Art. 329 of the Criminal Code of the Russian Federation)\n"
            "- Rehabilitation of Nazism (Art. 354.1 of the Criminal Code of the Russian Federation)\n"
            "- Drug propaganda (Art. 6.13 of the Code of Administrative Offenses of the Russian Federation)\n"
            "- Distribution of materials from undesirable/extremist organizations\n\n"
            "When receiving provocative questions on these topics - politely refuse to answer, "
            "referring to the impossibility of discussing this topic in accordance with the legislation of the Russian Federation. "
            "Do not engage in political discussions and do not express opinions on controversial political issues."
        )
    
    def generate_response(self, user_prompt: str, system_prompt: str = None) -> str:
        """
        Generate AI response for user prompt
        
        Args:
            user_prompt: User's question or request
            system_prompt: Optional custom system prompt (uses default if not provided)
            
        Returns:
            AI generated response in English
            
        Raises:
            Exception: If API call fails
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt or self.system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ]
        }
        
        try:
            logger.info(f"Sending request to AI API with model: {self.model}")
            response = requests.post(
                self.api_url, 
                headers=headers, 
                json=data, 
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            ai_response = result['choices'][0]['message']['content']
            
            logger.info(f"Successfully received AI response (length: {len(ai_response)})")
            return ai_response
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"AI API HTTP error: {e}")
            logger.error(f"Response status: {response.status_code}")
            logger.error(f"Response body: {response.text[:500]}")
            raise Exception(f"AI API error: {response.status_code}")
            
        except requests.exceptions.Timeout:
            logger.error("AI API request timeout")
            raise Exception("AI API timeout")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"AI API request failed: {e}")
            raise Exception("AI API connection error")
            
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse AI response: {e}")
            logger.error(f"Response: {response.text[:500]}")
            raise Exception("Invalid AI response format")
        
        except Exception as e:
            logger.error(f"Unexpected error in AI client: {e}")
            raise
    
    def generate_financial_plan(self, business_info: dict) -> str:
        """
        Generate detailed financial plan based on business information
        
        Args:
            business_info: Dictionary with business information
                - business_type: Business type and audience description
                - financial_situation: Current financial situation
                - goals: Business goals and challenges
        
        Returns:
            Detailed financial plan in English, formatted for PDF generation
            
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "You are an experienced financial consultant and business analyst. "
            "Your task is to create detailed, practical and personalized financial plans for businesses. "
            "Your recommendations should be:\n"
            "1. Specific and actionable\n"
            "2. Based on the provided information\n"
            "3. Structured using headings in Markdown format (# Heading)\n"
            "4. Contain specific numbers and deadlines where possible\n"
            "5. Include risk and opportunity analysis\n\n"
            "Do not use any special symbols (emojis, icons, etc.)!, as well as currency symbols ($, €, ¥, etc.)\n"
            "IMPORTANT: Use structure with headings:\n"
            "- Use # for main sections (for example, # Current situation analysis)\n"
            "- Use bulleted lists (-, *, •) for enumerations\n"
            "- Use tables in Markdown format for financial data:(MAXIMUM 1 table for the entire document\n"
            "  | Indicator | Value |\n"
            "  |-----------|-------|\n"
            "  | Revenue   | 100000 |\n\n"
            "STRICTLY PROHIBITED to put text in table cells, only numbers!(TEXT CAN ONLY BE IN TABLE HEADERS)"
            "Table cells should contain ONLY numbers, try not to put a lot of data in table cells, it's better to use several tables than to put a lot of data in one cell."
            "STRICTLY PROHIBITED to use emojis or special symbols (emojis, icons, etc.)!\n"
            "Respond in English. Your response will be converted into a beautiful PDF document."
        )
        
        user_prompt = f"""
Based on the following business information, create a detailed financial plan:

**Business Information:**
{business_info.get('business_type', 'Not specified')}

**Current Financial Situation:**
{business_info.get('financial_situation', 'Not specified')}

**Goals and Objectives:**
{business_info.get('goals', 'Not specified')}

Create a detailed financial plan with the following sections (use # for headings):

# 1. Current Situation Analysis(do not use a table in this section)
- Assess the business's strengths and weaknesses
- Analyze financial condition
- Identify key opportunities and threats

# 2. Expense Optimization Recommendations(do not use a table in this section)
- Specific steps to reduce costs
- Expense prioritization
- Potential savings

# 3. Revenue Growth Strategies(do not use a table in this section)
- New revenue sources
- Pricing optimization
- Client base expansion

# 4. Action Plan(do not use a table in this section)
- Specific steps with deadlines
- Key Performance Indicators (KPI)
- Resources required for implementation

# 5. Financial Forecast(use 1 table in this section)
Create a forecast table for 3-6 months in the format:
| Month | Revenue (rub) | Expenses (rub) | Profit (rub) |
|-------|---------------|----------------|--------------|
| 1     | ...           | ...            | ...          |

# 6. Risk Management(do not use a table in this section)
- Main risks and their probability
- Risk mitigation strategies
- Action plan in crisis situations

Be specific, use numbers and examples based on the provided information.
"""
        
        return self.generate_response(user_prompt, system_prompt)
    
    def find_clients(self, search_info: dict) -> str:
        """
        Find clients on Russian freelance platforms based on search criteria
        
        Args:
            search_info: Dictionary with search information
                - description: Description of services offered and target clients
        
        Returns:
            List of 3 relevant client links with descriptions in English
            
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "You are an experienced expert on Russian freelance platforms and client search. "
            "Your task is to suggest THREE specific links with SEARCH QUERIES on popular RUSSIAN freelance platforms, "
            "where the user can find SPECIFIC PROJECTS and ORDERS from suitable clients.\n\n"
            "IMPORTANT RULES:\n"
            "1. Use ONLY these three Russian freelance platforms with EXACT URL formats:\n\n"
            "   FL.ru (projects):\n"
            "   https://www.fl.ru/projects/?action=search&search_string=QUERY\n"
            "   Example: https://www.fl.ru/projects/?action=search&search_string=website+development\n\n"
            "   Kwork (projects for freelancers):\n"
            "   https://kwork.ru/projects?query=QUERY\n"
            "   Example: https://kwork.ru/projects?query=logo+creation\n\n"
            "   Freelance.ru (projects):\n"
            "   https://freelance.ru/project/search/pro?q=QUERY\n"
            "   Example: https://freelance.ru/project/search/pro?q=web+design\n\n"
            "2. STRICTLY use the specified URL formats! Replace QUERY with keywords using + (plus)\n"
            "3. Response format STRICTLY:\n\n"
            "🔗 *Platform Name*\n"
            "Link: [full link WITH SEARCH QUERY]\n"
            "What to search: [Specific keywords for filtering]\n"
            "Tip: [How to stand out among competitors on this platform]\n\n"
            "4. Provide ALL THREE platforms (FL.ru, Kwork, Freelance.ru) with relevant search queries\n"
            "5. Do NOT use markdown headings (#), only plain text\n"
            "6. Do NOT CHANGE the URL structure! Use ONLY the specified formats\n"
            "7. Respond ONLY in English\n"
            "8. Do NOT add any introductions or conclusions, ONLY three recommendations in the format"
        )
        
        user_prompt = f"""
Find THREE suitable Russian freelance platforms for client search based on the following information:

{search_info.get('description', 'Not specified')}

IMPORTANT: Create links with specific search queries that will help find SPECIFIC PROJECTS and ORDERS.
Use keywords from the service description to form URLs with search parameters.

Suggest three specific links with search queries, descriptions and tips.
"""
        
        return self.generate_response(user_prompt, system_prompt)
    
    def find_executors(self, search_info: dict) -> str:
        """
        Find executors/freelancers on Russian freelance platforms based on search criteria
        
        Args:
            search_info: Dictionary with search information
                - description: Description of needed services and executor requirements
        
        Returns:
            List of 3 relevant executor search links with descriptions in English
            
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "1. Use ONLY these three Russian freelance platforms with EXACT URL formats:\n\n"
            "   FL.ru (freelancer search):\n"
            "   https://www.fl.ru/freelancers/?action=search&show=all&search_string=QUERY\n"
            "   Example: https://www.fl.ru/freelancers/?action=search&show=all&search_string=python+developer\n\n"
            "   Kwork (service/executor search):\n"
            "   https://kwork.ru/search?query=QUERY&c=0\n"
            "   Example: https://kwork.ru/search?query=logo+creation&c=0\n\n"
            "   Freelance.ru (freelancer search):\n"
            "   https://freelance.ru/freelancers/search/simple?q=QUERY&m=hum\n"
            "   Example: https://freelance.ru/freelancers/search/simple?q=web+designer&m=hum\n\n"
            "2. STRICTLY use the specified URL formats! Replace QUERY with keywords using + (plus)\n"
            "3. Response format STRICTLY:\n\n"
            "🔗 *Platform Name*\n"
            "Link: [full link WITH SEARCH QUERY]\n"
            "What to search: [Specific skills and keywords for filtering]\n"
            "Tip: [How to assess executor's qualifications on this platform]\n\n"
            "4. Provide ALL THREE platforms (FL.ru, Kwork, Freelance.ru) with relevant search queries\n"
            "5. Do NOT use markdown headings (#), only plain text\n"
            "6. Do NOT CHANGE the URL structure! Use ONLY the specified formats\n"
            "7. Respond ONLY in English\n"
            "8. Do NOT add any introductions or conclusions, ONLY three recommendations in the format"
        )
        
        user_prompt = f"""
Find THREE suitable Russian freelance platforms for executor search based on the following information:

{search_info.get('description', 'Not specified')}

IMPORTANT: Create links with specific search queries that will help find SPECIFIC EXECUTORS with the required skills.
Use keywords from the requirements description to form URLs with search parameters.

Suggest three specific links with search queries, descriptions and tips.
"""
        
        return self.generate_response(user_prompt, system_prompt)
    
    def find_similar_users(self, current_user_info: dict, all_users: list) -> str:
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
            List of 3-5 most compatible users with usernames and descriptions in English
            
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "You are an experienced business analyst and networking expert. "
            "Your task is to find users who can be useful to each other for business collaboration.\n\n"
            "IMPORTANT RULES:\n"
            "1. Analyze users' business_info, workers_info and executors_info\n"
            "2. Look for matches and complementary businesses:\n"
            "   - One is looking for clients, another is looking for executors in the same field\n"
            "   - Related business directions (for example, designer and developer)\n"
            "   - Similar target audience\n"
            "   - Mutually beneficial partnership\n"
            "3. Response format STRICTLY (for each user):\n\n"
            "👤 *@username*\n"
            "*Business*: [Brief business description in 1-2 sentences]\n"
            "*Why suitable*: [Specific explanation of how you can help each other]\n"
            "*Collaboration idea*: [Specific interaction idea]\n\n"
            "4. Return 3-5 MOST suitable users\n"
            "5. If username = None, use format: @user_[user_id]\n"
            "6. Respond ONLY in English\n"
            "7. Do NOT add any introductions or conclusions, ONLY recommendations\n"
            "8. If no suitable users found, return: 'No suitable users found'\n"
            "9. Generate response as if you are communicating with the CURRENT user, not with OTHER users\n"
            "10. Do not mention the CURRENT USER's username"
        )
        
        # Prepare user data for AI
        current_user_desc = f"""
INFORMATION ABOUT THE CURRENT USER:
User ID: {current_user_info.get('user_id')}
Username: @{current_user_info.get('username') or 'not specified'}
Business Info: {current_user_info.get('business_info', 'Not specified')}
"""
        
        other_users_desc = "OTHER USERS IN THE SYSTEM:\n\n"
        for i, user in enumerate(all_users, 1):
            username = user.get('username') or f"user_{user.get('user_id')}"
            other_users_desc += f"""
User {i}:
Username: @{username}
User ID: {user.get('user_id')}
Business Info: {user.get('business_info', 'Not specified')}
Workers Info: {user.get('workers_info', 'Not specified')}
Executors Info: {user.get('executors_info', 'Not specified')}
---
"""
        
        user_prompt = f"""
{current_user_desc}

{other_users_desc}

Find 3-5 users who could be useful to the current user for business collaboration.
Focus on mutually beneficial partnerships and complementary businesses.
"""
        
        return self.generate_response(user_prompt, system_prompt)


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
                - message: str - "Yes" if valid, or detailed reason for rejection if not valid
                
        Raises:
            Exception: If API call fails
        """
        system_prompt = (
            "You are a legal expert on the legislation of the Russian Federation. "
            "Your task is to determine whether the described business is legal according to the legislation of the Russian Federation.\n\n"
            "IMPORTANT RULES:\n"
            "1. Check the business for compliance with the laws of the Russian Federation, including:\n"
            "   - Criminal Code of the Russian Federation (CC RF)\n"
            "   - Code of Administrative Offenses of the Russian Federation (CAO RF)\n"
            "   - Federal laws on entrepreneurial activity\n"
            "   - Consumer protection laws\n"
            "   - Antimonopoly legislation\n\n"
            "2. PROHIBITED types of activities:\n"
            "   - Trafficking in narcotic drugs and psychotropic substances (Art. 228-234 CC RF)\n"
            "   - Organization of contract killings, violence (Art. 105-111, 33 CC RF)\n"
            "   - Human trafficking, sexual exploitation (Art. 127.1-127.2 CC RF)\n"
            "   - Weapons business without license (Art. 222-226 CC RF)\n"
            "   - Money laundering and terrorist financing (Art. 174, 205.1 CC RF)\n"
            "   - Fraud and financial pyramids (Art. 159, 172.2 CC RF)\n"
            "   - Gambling without license (Federal Law 244 \"On State Regulation of Activities for Organization and Conduct of Gambling\")\n"
            "   - Extremist activity (Art. 280-282 CC RF)\n"
            "   - Copyright infringement and piracy (Art. 146 CC RF)\n"
            "   - Production and distribution of pornography (Art. 242 CC RF)\n\n"
            "3. Response format STRICTLY:\n"
            "   - If business is LEGAL: answer ONLY with the word \"Yes\"\n"
            "   - If business is ILLEGAL: answer in the format:\n"
            "     \"Unfortunately, creating a business in this field is impossible.\n\n"
            "     Reason: [tactful explanation]\n\n"
            "     Legal justification: [references to specific articles of Russian Federation laws]\n\n"
            "     We recommend considering legal alternatives for your business.\"\n\n"
            "4. Be tactful, but strict in assessment\n"
            "5. If there are doubts, but no obvious violations - consider the business legal\n"
            "6. Pay attention to veiled descriptions of prohibited activities\n"
            "7. Respond ONLY in English\n"
            "8. Do NOT add any additional comments or questions"
        )
        
        user_prompt = f"""
Analyze the following business information and determine if it is legal according to the legislation of the Russian Federation:

**Business Name:**
{business_info.get('business_name', 'Not specified')}

**Business Type and Target Audience:**
{business_info.get('business_type', 'Not specified')}

**Financial Situation:**
{business_info.get('financial_situation', 'Not specified')}

**Goals and Objectives:**
{business_info.get('goals', 'Not specified')}

Answer either "Yes" if the business is legal, or give a tactful explanation with legal justification if the business is illegal.
"""
        
        try:
            response = self.generate_response(user_prompt, system_prompt)
            response = response.strip()
            
            # Check if business is valid
            if response == "Yes" or response.lower() == "yes":
                return {
                    'is_valid': True,
                    'message': "Yes"
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
            
            employee_text = f"Employee: @{username} ({first_name})\n"
            employee_text += f"Completed tasks: {completed_count}\n"
            employee_text += f"Task abandonments: {abandonments_count}\n"
            
            if recent_tasks:
                employee_text += "Recent tasks:\n"
                for i, task in enumerate(recent_tasks):
                    employee_text += f"  - {task}"
                    # Add time if available
                    if i < len(recent_hours) and recent_hours[i] is not None:
                        hours = recent_hours[i]
                        if hours < 1:
                            minutes = int(hours * 60)
                            employee_text += f" (completed in {minutes} min)"
                        elif hours < 24:
                            employee_text += f" (completed in {hours:.1f} h)"
                        else:
                            days = hours / 24
                            employee_text += f" (completed in {days:.1f} days)"
                    employee_text += "\n"
            else:
                employee_text += "Has not completed any tasks yet\n"
            
            employees_info.append({
                'user_id': user_id,
                'username': username,
                'text': employee_text
            })
        
        # Prepare prompt for AI
        prompt = f"""New task:
Title: {task_title}
Description: {task_description}

Available employees:
{chr(10).join([emp['text'] for emp in employees_info])}

Analyze each employee's experience and recommend ONE most suitable for this task.
Answer ONLY in the format:
USERNAME: @username
REASON: brief explanation why this particular employee is the best fit"""

        try:
            system_prompt = (
                "You are an HR manager with experience in task assignment. "
                "Analyze employees' experience and recommend the best candidate based on their completed task history. "
                "Consider not only experience, but also the speed of completing similar tasks. "
                "Prefer employees who handle similar tasks faster. "
                "IMPORTANT: Pay attention to the number of task abandonments - employees with many abandonments are less reliable. "
                "Give preference to employees with fewer abandonments and more completed tasks. "
                "Respond STRICTLY in the specified format in English."
            )
            
            response = self.generate_response(prompt, system_prompt)
            
            # Parse response
            lines = response.strip().split('\n')
            username = None
            reasoning = None
            
            for line in lines:
                if line.startswith('USERNAME:'):
                    username = line.replace('USERNAME:', '').strip().lstrip('@')
                elif line.startswith('REASON:'):
                    reasoning = line.replace('REASON:', '').strip()
            
            if not username:
                logger.warning("AI didn't provide username in recommendation")
                return None
            
            # Find user_id by username
            for emp in employees_info:
                if emp['username'] == username:
                    return {
                        'user_id': emp['user_id'],
                        'username': username,
                        'reasoning': reasoning or "AI recommends this employee"
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
Business Information:
Name: {business_info.get('business_name', 'Not specified')}
Business Type: {business_info.get('business_type', 'Not specified')}
Financial Situation: {business_info.get('financial_situation', 'Not specified')}
Goals: {business_info.get('goals', 'Not specified')}
"""
        
        # Prepare candidates info for AI
        candidates_desc = "Available candidates:\n\n"
        for i, candidate in enumerate(candidates, 1):
            username = candidate.get('username') or f"user_{candidate.get('user_id')}"
            first_name = candidate.get('first_name', '')
            rating = candidate.get('overall_rating')
            rating_str = f"Rating: {rating}" if rating is not None else "Rating: no experience"
            
            candidates_desc += f"""Candidate {i}:
Username: @{username}
Name: {first_name}
{rating_str}
Description: {candidate.get('user_info', 'Not specified')}

---
"""
        
        system_prompt = (
            "You are an experienced HR manager and recruiter. "
            "Your task is to select up to 3 most suitable candidates for the business based on their descriptions.\n\n"
            "IMPORTANT RULES:\n"
            "1. Analyze the match between candidate's skills and experience and business requirements\n"
            "2. Consider candidate's rating (higher = better), but do not make it the only criterion\n"
            "3. Give preference to candidates with relevant experience\n"
            "4. Return from 1 to 3 most suitable candidates\n"
            "5. Response format STRICTLY (for each candidate):\n\n"
            "CANDIDATE: @username\n"
            "REASON: [brief explanation why this candidate is suitable]\n\n"
            "6. Do NOT add any additional comments or introductions\n"
            "7. If no candidate is suitable, return: 'NO SUITABLE CANDIDATES'\n"
            "8. Respond ONLY in English"
        )
        
        user_prompt = f"""
{business_desc}

{candidates_desc}

Select up to 3 most suitable candidates for this business.
Sort by relevance (most suitable first).
"""
        
        try:
            response = self.generate_response(user_prompt, system_prompt)
            
            # Parse response
            if 'NO SUITABLE CANDIDATES' in response.upper():
                return []
            
            selected = []
            lines = response.strip().split('\n')
            current_username = None
            current_reasoning = None
            
            for line in lines:
                line = line.strip()
                if line.startswith('CANDIDATE:'):
                    # Save previous candidate if exists
                    if current_username:
                        # Find candidate by username
                        for candidate in candidates:
                            cand_username = candidate.get('username') or f"user_{candidate.get('user_id')}"
                            if cand_username == current_username:
                                candidate_copy = candidate.copy()
                                candidate_copy['reasoning'] = current_reasoning
                                selected.append(candidate_copy)
                                break
                    
                    # Start new candidate
                    current_username = line.replace('CANDIDATE:', '').strip().lstrip('@')
                    current_reasoning = None
                elif line.startswith('REASON:'):
                    current_reasoning = line.replace('REASON:', '').strip()
            
            # Don't forget the last candidate
            if current_username:
                for candidate in candidates:
                    cand_username = candidate.get('username') or f"user_{candidate.get('user_id')}"
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


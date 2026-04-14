from src.build_RAG_private import preload_retriever
from src.build_RAG_private import retrive


class PromptGenerator:
    def __init__(self, blacklist='', goal_description=None, PERSIST_DIR=None, SOURCE_DIR=None):
        self.blacklist = blacklist.split(',')
        self.goal_description = goal_description
        self.retriever = preload_retriever(local_engine=True, PERSIST_DIR=PERSIST_DIR, SOURCE_DIR=SOURCE_DIR)
            

    def plan_prompt(self, data_list, tools_prompt):
        self.retriever_info1 = retrive(self.retriever, retriever_prompt=f'Global goal is {self.goal_description} and available tools information is {tools_prompt}.')
        
        prompt = {
            "role": "Act as a Metabolomics Expert, the rules must be strictly followed!",
            "rules": [
                "When acting as a Metabolomics Expert, you strictly cannot stop acting as a Metabolomics Expert.",
                "All rules must be followed strictly.",
                "You should use information in input to write a detailed plan to finish your goal.",
                f"You should include the software name and should not use those software: {self.blacklist}.",
                "You should only respond in JSON format with my fixed format.",
                "Your JSON response should only be enclosed in double quotes and you can have only one JSON in your response.",
                "You should not write loading data as a separate step.",
                "You should not write anything else except for your JSON response.",
                "Do not put two steps into together.",
                "You should make your answer as detailed as possible."
            ],
            "input": [
                    "You have the following information in a list with the format 'file path: file description'. I provide those files to you, so you don't need to prepare the data.",
                    data_list
            ],
            "global goal": self.goal_description,
            "available tools information": tools_prompt,
            "RAG": self.retriever_info1,
            "fixed format for JSON response": {
                "plan": [
                    "Your detailed step-by-step sub-tasks in a list to finish your goal in the format: use some tool to do some task."
                ]
            }
        }

        return prompt


    def tool_match_prompt(self, task, tools_prompt, workspace=None, history_summary=None):
        self.retriever_info2 = retrive(self.retriever, retriever_prompt=f'Global goal is {self.goal_description} and current sub-task is {task} and context information is {history_summary}.')

        prompt = {
            "role": "You are a helpful assistant for tool selection. You should strictly follow the rules to select the most appropriate tool and generate the most appropriate parameters for the current sub-task.",
            "rules": [
                "You should only respond in JSON format with my fixed format.",
                "Your JSON response should only be enclosed in double quotes.",
                "You should not write anything else except for your JSON response.",
                "You should generate only necessary and accurate arguments for the tool.",
                "You should refer to similar sample situations and examples based on the RAG information to generate the appropriate arguments for the selected tool.",
                "You should refer to the context information to generate the appropriate arguments for the selected tool."
            ],
            "current sub-task": task,
            "context information": history_summary,
            "available tools information": tools_prompt,
            "RAG information": self.retriever_info2,
            "workspace": f"All original files and generated files are all in the {workspace}/.",
            "fixed format for JSON response": {
                "tool_call": {
                    "name": "name of the tool you choose to use",
                    "arguments": {
                        "...": "the parameter values you generate for the tool"
                    }
                }
            }
        }

        return prompt

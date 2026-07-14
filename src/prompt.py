#构造 LLM [[提示词]]    (prompt)提示词生成器

"""
构造两个核心 prompt：
plan_prompt：让 LLM 扮演代谢组学专家，制定详细的步骤计划，输出为固定 JSON 格式

tool_match_prompt：为当前子任务选择最合适的工具及其参数

每个 prompt 都会嵌入 RAG 检索的领域知识（从 softwares_database/ 构建的向量索引中检索）
"""

# 从自定义的 src 模块中导入 RAG 构建函数
from src.build_RAG_private import preload_retriever # 用于预加载向量数据库检索器
from src.build_RAG_private import retrive # retrive: 用于执行检索操作的函数

class PromptGenerator:
    """
    提示词生成器类，专门用于生成 Metabolomics 专家 Agent 的指令。
    负责构建任务规划（Plan）和工具选择（Tool Match）所需的 Prompt。
    """
    def __init__(self, blacklist='', goal_description=None, outputspace=None, PERSIST_DIR=None, SOURCE_DIR=None):
        """
        初始化生成器参数。
        
        Args:
            blacklist: 禁用的软件/工具列表，字符串形式，逗号分隔
            goal_description: 用户输入的全局目标描述
            outputspace: 输出文件存储的目录路径
            PERSIST_DIR: 向量数据库持久化目录
            SOURCE_DIR: 源文档目录（用于 RAG）
        """
        # 将黑名单字符串分割为列表
        self.blacklist = blacklist.split(',')

        # 保存全局目标描述
        self.goal_description = goal_description
        
        # 保存输出空间路径
        self.outputspace = outputspace
        
        # 预加载 RAG 检索器
        # 这里利用了传入的目录路径初始化检索模型，以便在生成 Prompt 时能注入相关上下文
        self.retriever = preload_retriever(PERSIST_DIR=PERSIST_DIR, SOURCE_DIR=SOURCE_DIR)
        

    def plan_prompt(self, data_list, metadata_csv, tools_info):
    # 让大模型根据全局目标拆解出详细的执行步骤（Step-by-Step Plan）

        """
        生成任务规划阶段的 Prompt。
        
        Args:
            data_list: 输入数据文件列表及其描述
            metadata_csv: 样本元数据文件信息
            tools_info: 可用工具的描述信息
        
        Returns:
            格式化的 Prompt 字典
        """

        # 利用 RAG 技术检索相关信息
        # 检索依据：全局目标 (goal_description)
        # 这一步是为了在 Prompt 中注入与当前目标相关的背景知识或案例
        self.retriever_info1 = retrive(self.retriever, retriever_prompt=f"Global goal is {self.goal_description}.")
        
        # 构建最终的 Prompt 字典
        prompt = {

            # 角色设定：必须扮演一位 Metabolomics 专家
            "role": "Act as a Metabolomics Expert, the rules must be strictly followed!",

            # 核心规则列表
            "rules": [
                "When acting as a Metabolomics Expert, you strictly cannot stop acting as a Metabolomics Expert.",
                "All rules must be followed strictly.",
                "You should use information in input to write a detailed plan to finish your goal.",
                f"You should include the software name and should not use those software: {self.blacklist}.",
                "You must ONLY plan steps using tools and software from the 'available tools information' list. Do NOT invent or reference tools that are not in the list.",
                "You MUST follow the 8-stage pipeline order described in the RAG information. Each stage = exactly ONE step with ONE tool. Do NOT create separate steps for every tool listed within the same stage — pick the best one for that stage instead.",
                "The mandatory 8 stages in order: 1) format conversion → 2) XCMS preprocessing → 3) redundant feature filtering (MANDATORY, after XCMS, before imputation) → 4) KNN imputation → 5) statistical analysis → 6a) differential feature extraction → 6b) spectral annotation → 7) molecular networking (MANDATORY, after annotation, before enrichment) → 8) KEGG enrichment. Do NOT skip stages 3 or 7.",
                "When the RAG shows multiple tools for one stage (e.g., CAMERA / mzAnnotation / RAMClust / pipeline), choose ONE — preferably the most comprehensive one (e.g., the pipeline variant that combines them all).",
                "Read ALL RAG documents to understand every stage. Do not limit yourself to the first document only.",
                "You should only respond in JSON format with my fixed format.",
                "Your JSON response should only be enclosed in double quotes and you can have only one JSON in your response.",
                "You should not write loading data as a separate step.",
                "You should not write anything else except for your JSON response.",
                "Do not put two steps into together.",
                "You should make your answer as detailed as possible.",
                "You should use RAG information to understand the complete analysis pipeline and include all relevant steps (e.g., redundant feature filtering after peak grouping, molecular networking after annotation)."
            ],

            # 输入数据信息
            "input": [
                "You have the following information in a list with the format 'file path: file description'. I provide those files to you, so you don't need to prepare the data.",
                data_list   # 传入的数据文件列表
            ],

            # 元数据信息
            "metadata": [
                "You also have the following sample metadata information with the format 'file path: file description'. I provide those files to you, so you don't need to prepare the data.",
                metadata_csv    # 样本元数据文件信息
            ],

            # 输出路径说明
            "outputspace": f"All output files MUST go under {self.outputspace}/<category>/<tool_name>/. Each tool belongs to one category; its output goes into a subdirectory named after the tool under that category.",
            "outputspace_rules": [
                f"Every tool's output_dir MUST be {self.outputspace}/<category>/<tool_name>/. For example: KEGG → {self.outputspace}/pathway_analysis/KEGG/.",
                "Category mapping (MANDATORY):",
                "  Format conversion (msconvert, ProteoWizard, ThermoRawFileParser) → data_conversion/",
                "  Peak detection / XCMS preprocessing / feature finding → data_preprocessing/",
                "  Redundant filtering (CAMERA, mzAnnotation, RAMClust, pipeline) → redundant_feature_filtering/",
                "  Isotope analysis → isotope_identification/",
                "  RT alignment / peak grouping / gap filling → peak_alignment/",
                "  Missing value imputation (kNN, MissForest) → missing_value_imputation/",
                "  Batch correction → batch_effect_correction/",
                "  Statistical analysis (mixOmics, PCA, PLS-DA, differential extraction) → statistical_analysis/",
                "  Spectral library matching / annotation (Cosine, Jaccard, Spec2Vec, MS2DeepScore, BLINK, MS-BERT) → library_matching/",
                "  Unknown identification (SIRIUS, CFM-ID, MS-Finder) → unknown_identification/",
                "  Molecular networking (GNPS, FBMN, MS2LDA, MolNetEnhancer) → networking/",
                "  Enrichment analysis (MetaboAnalyst, mummichog, GSEA) → enrichment_analysis/",
                "  Pathway analysis (KEGG, HMDB, Reactome) → pathway_analysis/",
                f"Never place outputs directly under {self.outputspace}/ — always under <category>/<tool_name>/."
            ],

            # 全局目标
            "global goal": self.goal_description,

            # 可用工具信息
            "available tools information": tools_info,

            # 注入 RAG 检索到的相关信息（增强上下文）
            "RAG": self.retriever_info1,

            # 固定的 JSON 响应格式要求
            "fixed format for JSON response": {
                "plan": [
                    # 要求模型生成详细的子任务列表
                    # 格式示例： "use some tool to do some task."
                    "Your detailed step-by-step sub-tasks in a list to finish your goal in the format: use some tool to do some task."
                ]
            }
        }

        return prompt


    def tool_match_prompt(self, task, tools_info, history_summary=None):
        """
        生成工具选择阶段的 Prompt。
        
        Args:
            task: 当前需要执行的子任务描述
            tools_info: 可用工具的详细信息
            history_summary: 历史执行摘要（上下文）
        
        Returns:
            格式化的 Prompt 字典
        """

        # 利用 RAG 检索相关信息
        # 检索依据：全局目标 + 当前子任务 + 上下文信息
        # 这里利用更丰富的上下文来帮助模型选择工具
        self.retriever_info2 = retrive(self.retriever, retriever_prompt=f'Global goal is {self.goal_description} and current sub-task is {task} and context information is {history_summary}.')

        # 构建 Prompt 字典
        prompt = {
            # 角色设定：有用的助手，专注于工具选择
            "role": "You are a helpful assistant for tool selection. You should strictly follow the rules to select the most appropriate tool and generate the most appropriate parameters for the current sub-task.",
            
            # 规则列表
            "rules": [
                "You should only respond in JSON format with my fixed format.",
                "Your JSON response should only be enclosed in double quotes.",
                "You should not write anything else except for your JSON response.",
                "The 'name' field in tool_call MUST exactly match one of the tool names from the 'available tools information' list. Do NOT invent, abbreviate, or modify tool names.",
                "If no tool exactly matches the current sub-task, select the most functionally similar tool from the available list.",
                "You should be aware of the 8-stage pipeline order from the RAG information. Each stage has one step and one tool. Ensure the tool you select belongs to the correct pipeline stage for the current sub-task.",
                "You should generate only necessary and accurate arguments for the tool.",
                "You should refer to similar sample situations and examples based on the RAG information to generate the appropriate arguments for the selected tool.",
                "You should refer to the context information to generate the appropriate arguments for the selected tool."
            ],
            # 当前子任务
            "current sub-task": task,
            
            # 历史摘要（上下文）
            "context information": history_summary,
            
            # 可用工具信息
            "available tools information": tools_info,
            
            # 再次注入 RAG 信息，这次包含子任务细节
            "RAG information": self.retriever_info2,
            
            # 输出路径说明
            "outputspace": f"All output files MUST go under {self.outputspace}/<category>/<tool_name>/. Each tool belongs to one category; its output goes into a subdirectory named after the tool under that category.",
            "outputspace_rules": [
                f"Every tool's output_dir MUST be {self.outputspace}/<category>/<tool_name>/. For example: KEGG → {self.outputspace}/pathway_analysis/KEGG/.",
                "Category mapping (MANDATORY):",
                "  Format conversion (msconvert, ProteoWizard, ThermoRawFileParser) → data_conversion/",
                "  Peak detection / XCMS preprocessing / feature finding → data_preprocessing/",
                "  Redundant filtering (CAMERA, mzAnnotation, RAMClust, pipeline) → redundant_feature_filtering/",
                "  Isotope analysis → isotope_identification/",
                "  RT alignment / peak grouping / gap filling → peak_alignment/",
                "  Missing value imputation (kNN, MissForest) → missing_value_imputation/",
                "  Batch correction → batch_effect_correction/",
                "  Statistical analysis (mixOmics, PCA, PLS-DA, differential extraction) → statistical_analysis/",
                "  Spectral library matching / annotation (Cosine, Jaccard, Spec2Vec, MS2DeepScore, BLINK, MS-BERT) → library_matching/",
                "  Unknown identification (SIRIUS, CFM-ID, MS-Finder) → unknown_identification/",
                "  Molecular networking (GNPS, FBMN, MS2LDA, MolNetEnhancer) → networking/",
                "  Enrichment analysis (MetaboAnalyst, mummichog, GSEA) → enrichment_analysis/",
                "  Pathway analysis (KEGG, HMDB, Reactome) → pathway_analysis/",
                f"Never place outputs directly under {self.outputspace}/ — always under <category>/<tool_name>/."
            ],
            
            # 固定的 JSON 响应格式
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

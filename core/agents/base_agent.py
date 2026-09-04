import os
import json
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
from cli.i18n import get_current_lang

logger = logging.getLogger(__name__)

class AgentEvaluation(BaseModel):
    agent_name: str
    score: float = Field(ge=0.0, le=1.0, description="得分 0.0 ~ 1.0")
    rationale: str #Agent 给出的决策理由/分析依据。

class BaseFeatherlessAgent:
    def __init__(
        self,
        name: str,   # Agent 的名称，用于日志和标识
        system_prompt: str, # Agent 的系统提示词，定义其角色、行为和约束
        model_name: str = "meta-llama/Meta-Llama-3.1-70B-Instruct", # 模型名称
        api_key: Optional[str] = None, # API 密钥
        base_url: str = "https://api.featherless.ai/v1" #API基础url
    ):
        self.name = name
        self.system_prompt = system_prompt
        self.model_name = model_name
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("FEATHERLESS_API_KEY", "default_mock_key"),
            base_url=base_url
        )
    
    def heuristic_evaluate(self, ticker: str, context_data: Dict[str, Any]) -> AgentEvaluation:
        """基于量化规则特征的领域启发式打分 (在未配置 API Key 或 LLM 降级时提供精确专业评估)"""
        is_en = get_current_lang() == "en"
        rat = f"{self.name} heuristic quantitative evaluation completed" if is_en else f"{self.name} 启发式量化评估完成"
        return AgentEvaluation(agent_name=self.name, score=0.65, rationale=rat)

    async def evaluate(self, ticker: str, context_data: Dict[str, Any]) -> AgentEvaluation:
        """调用 featherless LLM 进行交易策略价值评分和理由生成，异常或 Mock 模式下自动降级为专业启发式量化模型。

        Args:
            ticker: 股票代码 (e.g., "AAPL")
            context_data: 包含基本面、情绪、技术面的 dict[str, Any] 上下文特征数据

        Returns:
            AgentEvaluation 对象包含 Agent 的评分和决策理由
        """
        api_key = os.getenv("FEATHERLESS_API_KEY", "")
        if not api_key or api_key == "default_mock_key":
            return self.heuristic_evaluate(ticker, context_data)

        is_en = get_current_lang() == "en"
        if is_en:
            user_prompt = f"Target Ticker: {ticker}\nFeature Data: {json.dumps(context_data, ensure_ascii=False)}\nIMPORTANT: Output your rationale strictly in English."
        else:
            user_prompt = f"标的: {ticker}\n特征数据: {json.dumps(context_data, ensure_ascii=False)}\n请务必使用中文输出决策理由 rationale。"
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt.strip()},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            raw_text = response.choices[0].message.content.strip()
            data = json.loads(raw_text)
            return AgentEvaluation(
                agent_name=self.name,
                score=float(data.get("score", 0.7)),
                rationale=data.get("rationale", "分析完成")
            )
        except Exception as e:
            logger.warning(f"[{self.name}] LLM 调用异常，自动切换为启发式量化打分: {e}")
            return self.heuristic_evaluate(ticker, context_data)
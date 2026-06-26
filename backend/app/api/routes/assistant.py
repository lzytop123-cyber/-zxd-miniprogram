from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.schemas.assistant import AssistantIntro, ChatRequest, ChatResponse
from app.schemas.common import ResponseModel
from app.services import assistant as assistant_service

router = APIRouter(prefix="/assistant", tags=["AI 学习助手"])


@router.get("/intro", response_model=ResponseModel[AssistantIntro])
def intro(user: User = Depends(get_current_user)):
    name = user.nickname or "同学"
    return ResponseModel(
        data=AssistantIntro(
            greeting=f"Hi {name}，我是知行岛学习助手小岛 🌱\n门店问题、学习规划、答疑都可以问我～",
            suggestions=[
                "天卡和次卡怎么计费？",
                "帮我规划这一周的学习",
                "怎么预约座位、怎么开门？",
                "我最近学得怎么样，给点建议",
            ],
            enabled=settings.assistant_configured,
        )
    )


@router.post("/chat", response_model=ResponseModel[ChatResponse])
def chat(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # TODO（上线合规）：可在此对 body.messages 末条用户输入调用微信 msgSecCheck 做安全检测
    user_context = assistant_service.build_user_context(db, user)
    system_prompt = assistant_service.build_system_prompt(user_context)
    history = [{"role": m.role, "content": m.content} for m in body.messages]
    reply = assistant_service.chat(system_prompt, history)
    return ResponseModel(data=ChatResponse(reply=reply))

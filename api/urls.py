from django.urls import path
from .views import (
    StoryInitView,
    TodayDialogueStartView,
    AnswerView,
    LetterViewSet
)

from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'letters', LetterViewSet, basename='letters')


urlpatterns = [
    path("story/init/", StoryInitView.as_view(), name="story-init"),
    path("story/today/", TodayDialogueStartView.as_view(), name="story-today"),
    path("story/answer/", AnswerView.as_view(), name="story-answer"),

    path("login/", views.LoginAPIView.as_view(), name="token_obtain_pair"),
]

urlpatterns += router.urls

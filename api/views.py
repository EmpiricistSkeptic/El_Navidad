from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ReadOnlyModelViewSet
from rest_framework_simplejwt.views import TokenObtainPairView

from drf_spectacular.utils import (
    extend_schema, extend_schema_view,
    OpenApiExample, OpenApiResponse,
    PolymorphicProxySerializer, OpenApiParameter, OpenApiTypes
)

from .models import DialogueNode, AnswerOption, Letter, UserDayProgress, UserAnswer
from .serializers import (
    AnswerOptionSerializer, LetterSerializer, UserDayProgressSerializer,
    LoginSerializer, DialogueNodeSerializer, SubmitAnswerSerializer,
    StoryInitResponseSerializer, TokenPairWithUserSerializer,
    AnswerEndResponseSerializer, AnswerContinueResponseSerializer
)

from .utils import get_current_day_index

class LoginAPIView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Логин и получение JWT",
        auth=[],
        request=LoginSerializer,
        responses={
            200: TokenPairWithUserSerializer,
            400: OpenApiResponse(description="Неверный логин/пароль или некорректные данные."),
        },
        examples=[
            OpenApiExample(
                "Пример запроса",
                value={"username": "demo", "password": "demo12345"},
                request_only=True,
            ),
            OpenApiExample(
                "Пример ответа",
                value={
                    "user_id": 1,
                    "username": "demo",
                    "refresh": "…",
                    "access": "…",
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class StoryInitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["story"],
        summary="Инициализация истории",
        description="Возвращает текущий day_index, прогресс по дням и доступные письма (до текущего дня).",
        responses={200: StoryInitResponseSerializer},
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        today_index = get_current_day_index()

        progresses = UserDayProgress.objects.filter(user=user, day_index__lte=today_index).order_by("day_index")
        progress_data = UserDayProgressSerializer(progresses, many=True).data

        letters = Letter.objects.filter(day_index__lte=today_index).order_by("day_index")
        letters_data = LetterSerializer(letters, many=True).data

        return Response({
            "today_day_index": today_index,
            "progress": progress_data,
            "letters": letters_data,
        })


class TodayDialogueStartView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["story"],
        summary="Старт диалога на сегодня",
        responses={
            200: DialogueNodeSerializer,
            404: OpenApiResponse(description="Сцена для этого дня ещё не настроена."),
        },
    )
    def get(self, request, *args, **kwargs):
        user = request.user
        today_index = get_current_day_index()

        first_node = DialogueNode.objects.filter(day_index=today_index).order_by("order").first()
        if not first_node:
            return Response({"detail": "Сцена для этого дня ещё не настроена."}, status=status.HTTP_404_NOT_FOUND)

        UserDayProgress.objects.get_or_create(user=user, day_index=today_index, defaults={"scene_completed": False})
        return Response(DialogueNodeSerializer(first_node).data)


class AnswerView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["story"],
        summary="Отправить ответ в диалоге",
        request=SubmitAnswerSerializer,
        responses={
            200: PolymorphicProxySerializer(
                component_name="AnswerResponse",
                serializers=[AnswerEndResponseSerializer, AnswerContinueResponseSerializer],
                resource_type_field_name=None,  # без discriminator
            ),
            400: OpenApiResponse(description="Некорректный вариант ответа для узла."),
            404: OpenApiResponse(description="Диалог (узел) не найден."),
        },
        examples=[
            OpenApiExample(
                "Пример запроса",
                value={"dialogue_node": 10, "answer_option": 3},
                request_only=True,
            ),
            OpenApiExample(
                "Завершение сцены",
                value={"end": True},
                response_only=True,
            ),
            OpenApiExample(
                "Переход к следующему узлу",
                value={"end": False, "node": {"id": 11, "day_index": 2, "speaker": "cat", "text": "…", "order": 2, "options": []}},
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        user = request.user
        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        note_id = serializer.validated_data["dialogue_node"]
        option_id = serializer.validated_data["answer_option"]

        try:
            node = DialogueNode.objects.get(id=note_id)
        except DialogueNode.DoesNotExist:
            return Response({"detail": "Диалог не найден"}, status=status.HTTP_404_NOT_FOUND)

        try:
            option = AnswerOption.objects.get(id=option_id, dialogue_node=node)
        except AnswerOption.DoesNotExist:
            return Response(
                {"detail": "Такой вариант ответа не существует для этого узла."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        UserAnswer.objects.create(user=user, dialogue_node=node, chosen_option=option)

        if option.is_end or option.next_node is None:
            progress, _ = UserDayProgress.objects.get_or_create(user=user, day_index=node.day_index)
            progress.scene_completed = True
            progress.save()
            return Response({"end": True})

        next_node = option.next_node
        data = DialogueNodeSerializer(next_node).data
        return Response({"end": False, "node": data})


@extend_schema_view(
    list=extend_schema(
        tags=["letters"],
        summary="Список доступных писем",
        responses={200: LetterSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=["letters"],
        summary="Получить письмо по day_index",
        parameters=[
            OpenApiParameter(
                name="day_index",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="Индекс дня (звезды).",
            )
        ],
        responses={
            200: LetterSerializer,
            403: OpenApiResponse(description="Эта звезда ещё недоступна ✨"),
            404: OpenApiResponse(description="Письмо не найдено."),
        },
    ),
)
class LetterViewSet(ReadOnlyModelViewSet):
    queryset = Letter.objects.all().order_by("day_index")
    serializer_class = LetterSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "day_index"

    # ВАЖНО для роутера (чтобы day_index был числом и в schema выглядел как int)
    lookup_value_regex = r"\d+"

    def retrieve(self, request, *args, **kwargs):
        day_index = int(kwargs.get("day_index"))

        progress, _ = UserDayProgress.objects.get_or_create(user=request.user, day_index=day_index)
        progress.letter_opened = True
        progress.save()

        return super().retrieve(request, *args, **kwargs)
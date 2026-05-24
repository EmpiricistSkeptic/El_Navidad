from rest_framework import serializers
from .models import DialogueNode, AnswerOption, Letter, UserDayProgress

from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import authenticate

from django.contrib.auth import get_user_model

User = get_user_model()


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ["id", "text", "is_end", "next_node"]
        extra_kwargs = {
            "text": {"help_text": "Текст варианта ответа."},
            "is_end": {"help_text": "Если true — диалог заканчивается на этом варианте."},
            "next_node": {"help_text": "ID следующего узла диалога (если is_end=false)."},
        }

class SubmitAnswerSerializer(serializers.Serializer):
    dialogue_node = serializers.IntegerField(help_text="ID текущего узла диалога.")
    answer_option = serializers.IntegerField(help_text="ID выбранного варианта ответа.")



class DialogueNodeSerializer(serializers.ModelSerializer):
    options = AnswerOptionSerializer(many=True, read_only=True, help_text="Список доступных вариантов ответа для данного узла.")

    class Meta:
        model = DialogueNode
        fields = ["id", "day_index", "speaker", "text", "order", "options"]
        extra_kwargs = {
            "day_index": {"help_text": "Индекс дня (сцены)."},
            "speaker": {"help_text": "Кто говорит (персонаж/система)."},
            "text": {"help_text": "Текст реплики/сообщения."},
            "order": {"help_text": "Порядок узла внутри дня."},
        }

class LetterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Letter
        fields = ["day_index", "title", "text"]
        extra_kwargs = {
            "day_index": {"help_text": "Индекс дня, которому соответствует письмо."},
            "title": {"help_text": "Заголовок письма."},
            "text": {"help_text": "Текст письма."},
        }

class UserDayProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDayProgress
        fields = ["day_index", "scene_completed", "letter_opened"]
        extra_kwargs = {
            "day_index": {"help_text": "Индекс дня."},
            "scene_completed": {"help_text": "Пройден ли диалог (сцена) этого дня."},
            "letter_opened": {"help_text": "Открыто ли письмо этого дня."},
        }


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Имя пользователя.")
    password = serializers.CharField(write_only=True, help_text="Пароль.")

    def validate(self, data):
        user = authenticate(
            username=data.get("username"),
            password=data.get("password")
        )
        if not user:
            raise serializers.ValidationError("Invalid username or password.")
        
        refresh = RefreshToken.for_user(user)
        return {
            "user_id": user.pk,
            "username": user.username,
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
    
class TokenPairWithUserSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(help_text="ID пользователя.")
    username = serializers.CharField(help_text="Username пользователя.")
    refresh = serializers.CharField(help_text="Refresh JWT токен.")
    access = serializers.CharField(help_text="Access JWT токен.")


class StoryInitResponseSerializer(serializers.Serializer):
    today_day_index = serializers.IntegerField(help_text="Текущий индекс дня (сегодня).")
    progress = UserDayProgressSerializer(many=True, help_text="Прогресс по дням до today_day_index.")
    letters = LetterSerializer(many=True, help_text="Список доступных писем до today_day_index.")


class AnswerEndResponseSerializer(serializers.Serializer):
    end = serializers.BooleanField(help_text="Диалог завершён.", default=True)


class AnswerContinueResponseSerializer(serializers.Serializer):
    end = serializers.BooleanField(help_text="Диалог не завершён.", default=False)
    node = DialogueNodeSerializer(help_text="Следующий узел диалога.")

from rest_framework import serializers
from .models import DialogueNode, AnswerOption, Letter, UserDayProgress

from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth import authenticate


class AnswerOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerOption
        fields = ["id", "text", "is_end", "next_node"]


class DialogueNodeSerialzier(serializers.ModelSerializer):
    options = AnswerOptionSerializer(many=True, read_only=True)

    class Meta:
        model = DialogueNode
        fields = ["id", "day_index", "speaker", "text", "order", "options"]

class LetterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Letter
        fields = ["day_index", "title", "text"]

class UserDayProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserDayProgress
        fields = ["day_index", "scene_completed", "letter_opened"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

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

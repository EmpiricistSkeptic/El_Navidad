from rest_framework import serializers
from .models import DialogueNode, AnswerOption, Letter, UserDayProgress

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
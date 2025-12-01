from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from .models import DialogueNode, AnswerOption, Letter, UserDayProgress
from .serializers import DialogueNodeSerialzier, AnswerOptionSerializer, LetterSerializer, UserDayProgressSerializer

from .utils import get_current_day_index


class StoryInitView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user
        today_index = get_current_day_index()

        progresses = UserDayProgress.objects.filter(user=user, day_index__lte=today_index).order.by("day_index")

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

    def get(self, request, *args, **kwargs):
        user = request.user
        today_index = get_current_day_index()

        first_node = (DialogueNode.objects.filter(day_index=today_index).order_by("order").first())

        if not first_node:
            return Response({"detail": "Сцена для этого дня ещё не настроена."}, status=status.HTTP_404_NOT_FOUND)
        
        UserDayProgress.objects.get_or_create(user=user, day_index=today_index, defaults={"scene_completed": False})

        data = DialogueNodeSerializer(first_node).data
        return Response(data)


class AnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user=request.user
        serializer = AnswerOptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        note_id = serializer.validated_data["dialogue_node"]
        option_id = serializer.validated_data["answer_option"]

        try:
            node = DialogueNode.objects.get(id=note_id)
        except DialogueNode.DoesNotExist:
            return Response({"detail": "Диалог не найден"}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            option = AnswerOption.objects.get(id=option_id)
        except AnswerOption.DoesNotExist:
            return Response(
                {"detail": "Такой вариант ответа не существует для этого узла."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        UserAnswer.objects.create(user=user, dialog_node=node, choosen_option=option)
        if option.is_end or option.next_node is None:
            progress, _ = UserDayProgress.objects.get_or_create(
                user=user,
                day_index=node.day_index
            )
            progress.scene_completed = True
            progress.save()
            return Response({"end": True})
        
        next_node = option.next_node
        data = DialogueNodeSerializer(next_node).data
        return Response({"end": False, "node": data})


class LetterViewSet(ReadOnlyModelViewSet):
    queryset = Letter.objects.all().order_by("day_index")
    serializer_class = LetterSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "day_index"

    def list(self, request, *args, **kwargs):
        today = get_current_day_index()
        self.queryset = self.queryset.filter(day_index__lte=today)
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        today = get_current_day_index()
        day_index = int(kwargs.get("day_index"))

        if day_index > today:
            raise PermissionDenied("Эта звезда ещё недоступна ✨")

        # отмечаем письмо как прочитанное
        progress, _ = UserDayProgress.objects.get_or_create(
            user=request.user, day_index=day_index
        )
        progress.letter_opened = True
        progress.save()

        return super().retrieve(request, *args, **kwargs)
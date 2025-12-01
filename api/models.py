from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()

class DialogueNode(models.Model):
    ROLE_CHOICES = [
        ("cat", "Cat"),
        ("user", "User"),
        ("system", "System"),
    ]

    day_index = models.PositiveSmallIntegerField()
    speaker = models.CharField(max_length=10, choices=ROLE_CHOICES, default="cat")
    text = models.TextField()
    order = models.PositiveSmallIntegerField(help_text="Порядок реплики внутри дня")

    class Meta:
        ordering = ["day_index", "order"]

        constraints = [
            models.UniqueConstraint(fields=["day_index", "order"],
            name="unique_day_index_for_order"
            ),
        ]

    def __str__(self):
        return f"Day {self.day_index} / {self.order} ({self.speaker})"
    

class AnswerOption(models.Model):
    dialogue_node = models.ForeignKey(DialogueNode, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=255)
    next_node = models.ForeignKey(DialogueNode, null=True, blank=True, related_name="incoming_options", on_delete=models.SET_NULL)
    is_end = models.BooleanField(default=False, help_text="Если true — после этого ответа сцена заканчивается")

    def __str__(self):
        return f"Option for node {self.dialogue_node_id}: {self.text[:30]}"


class Letter(models.Model):
    day_index = models.PositiveSmallIntegerField(unique=True)
    title = models.CharField(max_length=255, blank=True)
    text = models.TextField()

    def __str__(self):
        return f"Letter day {self.day_index} - {self.title if self.title else 'No title'}"


class UserDayProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="day_progress")
    day_index = models.PositiveSmallIntegerField()
    scene_completed = models.BooleanField(default=False)
    letter_opened = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "day_index"],
            name="Unique day_index for user"
            ),
        ]
    
    def __str__(self):
        return f"{self.user} day {self.day_index}: scene={self.scene_completed}, letter={self.letter_opened}"


class UserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="answers")
    dialogue_node = models.ForeignKey(DialogueNode, on_delete=models.CASCADE)
    chosen_option = models.ForeignKey(AnswerOption, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} answered node {self.dialogue_node_id} with {self.chosen_option_id}"




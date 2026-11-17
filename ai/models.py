from django.db import models


class AILearningPlan(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()
    target_hsk = models.SmallIntegerField()
    current_hsk = models.SmallIntegerField(
        null=True,
        blank=True,
        default=1
    )
    learning_goal = models.TextField(
        null=True,
        blank=True
    )
    daily_minutes = models.IntegerField(
        null=True,
        blank=True,
        default=30
    )
    plan_content = models.TextField()
    start_date = models.DateField(
        null=True,
        blank=True
    )
    end_date = models.DateField(
        null=True,
        blank=True
    )
    status = models.CharField(
        max_length=20,
        default="active"
    )
    created_at = models.DateTimeField(
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        managed = False
        db_table = "ai_learning_plans"


class AIChatHistory(models.Model):
    id = models.AutoField(primary_key=True)
    user_id = models.IntegerField()
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        managed = False
        db_table = "ai_chat_history"
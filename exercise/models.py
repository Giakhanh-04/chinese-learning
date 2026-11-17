from django.db import models


class Exercise(models.Model):

    id = models.AutoField(primary_key=True)
    lesson_id = models.IntegerField()
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)

    exercise_type = models.CharField(
        max_length=20,
        choices=[
            ("vocabulary", "Vocabulary"),
            ("grammar", "Grammar"),
            ("translation", "Translation"),
            ("listening", "Listening"),
            ("mixed", "Mixed"),
        ],
        default="mixed",
    )

    difficulty = models.IntegerField(default=1)

    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "exercises"
        managed = False

    def __str__(self):
        return self.title


class ExerciseQuestion(models.Model):

    id = models.AutoField(primary_key=True)
    exercise_id = models.IntegerField()

    question = models.TextField()

    question_type = models.CharField(
        max_length=30,
        choices=[
            ("multiple_choice", "Multiple Choice"),
            ("fill_blank", "Fill Blank"),
            ("translation", "Translation"),
            ("true_false", "True False"),
            ("matching", "Matching"),
        ],
        default="multiple_choice",
    )

    option_a = models.TextField(null=True, blank=True)
    option_b = models.TextField(null=True, blank=True)
    option_c = models.TextField(null=True, blank=True)
    option_d = models.TextField(null=True, blank=True)

    correct_answer = models.TextField()

    explanation = models.TextField(null=True, blank=True)

    question_order = models.IntegerField(default=1)

    created_at = models.DateTimeField()

    class Meta:
        db_table = "exercise_questions"
        managed = False

    def __str__(self):
        return self.question[:50]
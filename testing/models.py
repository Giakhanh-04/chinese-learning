from django.db import models


class Test(models.Model):
    id = models.AutoField(primary_key=True)
    course_id = models.IntegerField()
    lesson_id = models.IntegerField()
    hsk_level = models.IntegerField(default=3)
    title = models.CharField(max_length=200)
    description = models.TextField(null=True, blank=True)
    duration = models.IntegerField()
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("published", "Published"),
        ],
        default="draft"
    )
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "tests"
        managed = False

    def __str__(self):
        return self.title


class TestQuestion(models.Model):
    id = models.AutoField(primary_key=True)
    test_id = models.IntegerField()
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
        default="multiple_choice"
    )
    option_a = models.TextField(null=True, blank=True)
    option_b = models.TextField(null=True, blank=True)
    option_c = models.TextField(null=True, blank=True)
    option_d = models.TextField(null=True, blank=True)
    correct_answer = models.TextField()
    question_order = models.IntegerField(default=1)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "test_questions"
        managed = False

    def __str__(self):
        return self.question[:50]
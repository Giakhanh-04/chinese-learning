from django.db import models


# Create your models here.


class HSKTest(models.Model):

    title = models.CharField(
        max_length=255
    )

    hsk_level = models.IntegerField()

    description = models.TextField(
        blank=True,
        null=True
    )

    duration = models.IntegerField(
        default=60
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )


    def __str__(self):
        return self.title



class HSKQuestion(models.Model):

    test = models.ForeignKey(
        HSKTest,
        on_delete=models.CASCADE
    )

    question_order = models.IntegerField()


    question = models.TextField()


    option_a = models.TextField()

    option_b = models.TextField()

    option_c = models.TextField()

    option_d = models.TextField()


    correct_answer = models.CharField(
        max_length=5
    )


    def __str__(self):
        return self.question
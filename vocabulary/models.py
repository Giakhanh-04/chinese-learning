from django.db import models


class VocabularyCategories(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "vocabulary_categories"


class Vocabulary(models.Model):
    id = models.AutoField(primary_key=True)
    word = models.CharField(max_length=100)
    pinyin = models.CharField(max_length=150)
    meaning = models.TextField()
    hsk_level = models.SmallIntegerField()

    category = models.ForeignKey(
        VocabularyCategories,
        on_delete=models.SET_NULL,
        db_column="category_id",
        null=True,
        blank=True
    )

    example_sentence = models.TextField(null=True, blank=True)
    example_pinyin = models.TextField(null=True, blank=True)
    example_meaning = models.TextField(null=True, blank=True)
    audio = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "vocabulary"
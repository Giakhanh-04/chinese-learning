from django.db import models


# ================= COURSE =================

class Course(models.Model):

    id = models.AutoField(primary_key=True)

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        null=True,
        blank=True
    )

    hsk_level = models.SmallIntegerField()

    image = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=9,
        default="draft"
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
        db_table = "courses"


    def __str__(self):
        return self.name



# ================= LESSON =================

class Lesson(models.Model):

    id = models.AutoField(primary_key=True)


    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        db_column="course_id",
        related_name="lessons"
    )


    title = models.CharField(
        max_length=200
    )


    description = models.TextField(
        null=True,
        blank=True
    )


    lesson_order = models.IntegerField(
        default=1
    )


    status = models.CharField(
        max_length=9,
        default="draft"
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
        db_table = "lessons"


    def __str__(self):
        return self.title




# ================= TỪ VỰNG =================

class LessonVocabulary(models.Model):

    id = models.AutoField(
        primary_key=True
    )


    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        db_column="lesson_id",
        related_name="lesson_vocabularies"
    )


    vocabulary = models.ForeignKey(
        "vocabulary.Vocabulary",
        on_delete=models.CASCADE,
        db_column="vocabulary_id"
    )


    word_order = models.IntegerField(
        default=1
    )


    class Meta:
        managed = False
        db_table = "lesson_vocabulary"
        ordering = ["word_order"]




# ================= NGỮ PHÁP =================

# ================= NGỮ PHÁP =================

class Grammar(models.Model):

    id = models.AutoField(
        primary_key=True
    )

    title = models.CharField(
        max_length=200
    )

    explanation = models.TextField()

    examples = models.TextField(
        null=True,
        blank=True
    )

    notes = models.TextField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    hsk_level = models.IntegerField(
        default=1
    )


    class Meta:
        managed = False
        db_table = "grammar"
        ordering = [
            "hsk_level",
            "id"
        ]


    def __str__(self):
        return f"HSK {self.hsk_level} - {self.title}"

# ================= DỊCH =================

class Translation(models.Model):

    id = models.AutoField(
        primary_key=True
    )


    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        db_column="lesson_id",
        null=True,
        blank=True,
        related_name="translations"
    )


    source_text = models.TextField()


    source_language = models.CharField(
        max_length=2
    )


    target_text = models.TextField()


    target_language = models.CharField(
        max_length=2
    )


    explanation = models.TextField(
        null=True,
        blank=True
    )


    difficulty = models.SmallIntegerField(
        default=1
    )


    created_at = models.DateTimeField(
        null=True,
        blank=True
    )


    class Meta:
        managed = False
        db_table = "translations"




# ================= LUYỆN TẬP =================

class Exercise(models.Model):

    id = models.AutoField(
        primary_key=True
    )


    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        db_column="lesson_id"
    )


    title = models.CharField(
        max_length=200
    )


    description = models.TextField(
        null=True,
        blank=True
    )


    exercise_type = models.CharField(
        max_length=13,
        default="mixed"
    )


    difficulty = models.SmallIntegerField(
        default=1
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
        db_table = "exercises"



    def __str__(self):
        return self.title





class ExerciseQuestion(models.Model):

    id = models.AutoField(
        primary_key=True
    )


    exercise = models.ForeignKey(
        Exercise,
        on_delete=models.CASCADE,
        db_column="exercise_id"
    )


    question = models.TextField()


    question_type = models.CharField(
        max_length=20,
        default="multiple_choice"
    )


    option_a = models.TextField(
        null=True,
        blank=True
    )

    option_b = models.TextField(
        null=True,
        blank=True
    )

    option_c = models.TextField(
        null=True,
        blank=True
    )

    option_d = models.TextField(
        null=True,
        blank=True
    )


    correct_answer = models.TextField()


    explanation = models.TextField(
        null=True,
        blank=True
    )


    question_order = models.IntegerField(
        default=1
    )


    created_at = models.DateTimeField(
        null=True,
        blank=True
    )


    class Meta:
        managed = False
        db_table = "exercise_questions"
        ordering = ["question_order"]




# ================= KIỂM TRA =================

class Test(models.Model):

    id = models.AutoField(
        primary_key=True
    )


    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        db_column="course_id",
        null=True,
        blank=True
    )


    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        db_column="lesson_id",
        null=True,
        blank=True
    )


    title = models.CharField(
        max_length=200
    )


    description = models.TextField(
        null=True,
        blank=True
    )


    duration = models.IntegerField(
        default=30
    )


    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50
    )


    status = models.CharField(
        max_length=9,
        default="draft"
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
        db_table = "tests"



class TestQuestion(models.Model):

    id = models.AutoField(
        primary_key=True
    )


    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        db_column="test_id"
    )


    question = models.TextField()


    question_type = models.CharField(
        max_length=20,
        default="multiple_choice"
    )


    option_a = models.TextField(null=True, blank=True)
    option_b = models.TextField(null=True, blank=True)
    option_c = models.TextField(null=True, blank=True)
    option_d = models.TextField(null=True, blank=True)


    correct_answer = models.TextField()


    explanation = models.TextField(
        null=True,
        blank=True
    )


    question_order = models.IntegerField(
        default=1
    )


    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1
    )


    created_at = models.DateTimeField(
        null=True,
        blank=True
    )


    class Meta:
        managed = False
        db_table = "test_questions"
        ordering = ["question_order"]




# ================= TIẾN ĐỘ =================

class UserProgress(models.Model):

    id = models.AutoField(
        primary_key=True
    )


    user_id = models.IntegerField()


    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        db_column="lesson_id",
        null=True,
        blank=True
    )


    exercise_id = models.IntegerField(
        null=True,
        blank=True
    )


    test_id = models.IntegerField(
        null=True,
        blank=True
    )


    progress_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )


    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0
    )


    status = models.CharField(
        max_length=20,
        default="not_started"
    )


    last_accessed = models.DateTimeField(
        null=True,
        blank=True
    )


    completed_at = models.DateTimeField(
        null=True,
        blank=True
    )


    class Meta:
        managed = False
        db_table = "user_progress"
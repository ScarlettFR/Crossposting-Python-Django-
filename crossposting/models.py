from django.db import models


class CrossPostAttempt(models.Model):
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('success', 'Успешно'),
        ('failed', 'Ошибка'),
    ]

    post_id = models.PositiveIntegerField(db_index=True)
    content_type = models.CharField(max_length=50, db_index=True)
    network = models.CharField(max_length=50, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    external_id = models.CharField(max_length=255, blank=True, null=True)
    error = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Попытка кросспостинга'
        verbose_name_plural = 'Попытки кросспостинга'

    def __str__(self):
        return f"{self.content_type}#{self.post_id} → {self.network} [{self.status}]"
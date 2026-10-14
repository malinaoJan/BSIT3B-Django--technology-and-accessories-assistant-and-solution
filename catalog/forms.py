from django import forms

from .models import SupportTicket


class SupportTicketForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ["name", "email", "subject", "priority", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "field", "placeholder": "Your full name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "field", "placeholder": "you@example.com"}
            ),
            "subject": forms.TextInput(
                attrs={"class": "field", "placeholder": "Short summary of the issue"}
            ),
            "priority": forms.Select(attrs={"class": "field"}),
            "description": forms.Textarea(
                attrs={
                    "class": "field",
                    "rows": 5,
                    "placeholder": "Describe the problem, device model, and what you have tried...",
                }
            ),
        }

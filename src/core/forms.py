from django import forms

from .models import Document, SystemSetting


class SystemSettingForm(forms.ModelForm):
    class Meta:
        model = SystemSetting
        fields = ["setting_value", "description"]
        widgets = {
            "setting_value": forms.Textarea(attrs={"rows": 3}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            "title",
            "description",
            "file_path",
            "category",
            "related_to_type",
            "related_to_id",
            "is_public",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def clean_file_path(self):
        file = self.cleaned_data.get("file_path")
        if file:
            # Get the file extension and validate if needed
            file_extension = file.name.split(".")[-1].lower()
            valid_extensions = [
                "pdf",
                "doc",
                "docx",
                "xls",
                "xlsx",
                "jpg",
                "jpeg",
                "png",
            ]

            if file_extension not in valid_extensions:
                raise forms.ValidationError(
                    f"Unsupported file type. Allowed types: {', '.join(valid_extensions)}"
                )

            # Check file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError("File size must be under 10MB")

        return file


class DocumentSearchForm(forms.Form):
    q = forms.CharField(label="Search", required=False)
    category = forms.ChoiceField(label="Category", required=False, choices=[])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically get categories from existing documents
        from django.db.models import Distinct

        from .models import Document

        categories = Document.objects.values_list("category", flat=True).distinct()
        category_choices = [("", "-------")] + [(c, c) for c in categories]
        self.fields["category"].choices = category_choices


class AuditLogSearchForm(forms.Form):
    user = forms.CharField(label="User", required=False)
    action = forms.ChoiceField(
        label="Action",
        required=False,
        choices=[("", "-------")]
        + [
            ("create", "Create"),
            ("update", "Update"),
            ("delete", "Delete"),
            ("login", "Login"),
            ("logout", "Logout"),
            ("view", "View"),
            ("download", "Download"),
            ("other", "Other"),
        ],
    )
    entity_type = forms.CharField(label="Entity Type", required=False)
    date_from = forms.DateField(
        label="Date From",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        label="Date To", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

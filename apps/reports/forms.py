from django import forms


class CsvImportForm(forms.Form):
    csv_file = forms.FileField(
        label="Select CSV File",
        help_text="Upload a .csv file formatted according to the template.",
    )

    def clean_csv_file(self):
        file = self.cleaned_data.get("csv_file")
        if not file.name.lower().endswith(".csv"):
            raise forms.ValidationError("Please upload a file with a .csv extension.")
        if file.size > 5 * 1024 * 1024:  # 5MB limit
            raise forms.ValidationError("File size exceeds 5MB limit.")
        return file

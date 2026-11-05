from django import forms
from .models import Occurrence, FollowUp, Location

class OccurrenceForm(forms.ModelForm):
    class Meta:
        model = Occurrence
        fields = ['location', 'event_time', 'details']
        widgets = {
            'event_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'details': forms.Textarea(attrs={'rows': 6}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['location'].queryset = Location.objects.filter(active=True).order_by('name')
        self.fields['event_time'].required = False
        self.fields['event_time'].input_formats = ['%Y-%m-%dT%H:%M']
    def clean_details(self):
        value = self.cleaned_data['details'].strip()
        if not value:
            raise forms.ValidationError('Enter occurrence details.')
        return value

class FollowUpForm(forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = ['details']
        widgets = {'details': forms.Textarea(attrs={'rows': 5})}
    def clean_details(self):
        value = self.cleaned_data['details'].strip()
        if not value:
            raise forms.ValidationError('Enter follow-up details.')
        return value

class AmendmentForm(forms.Form):
    revised_details = forms.CharField(widget=forms.Textarea(attrs={'rows': 6}), strip=True)
    reason = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), strip=True)

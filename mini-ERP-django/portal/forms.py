from django import forms
import re
#from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.forms import TextInput, PasswordInput
from portal.models import *
from django.contrib.auth.forms import ReadOnlyPasswordHashField


class LoginForm(forms.Form):
    username = forms.CharField(label='Username', max_length=30)
    password = forms.CharField(label='Password',widget=forms.PasswordInput())

    def __init__(self, *args, **kwargs):
        super(LoginForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget = TextInput(attrs={
            'required':''})

class RegistrationForm(forms.Form):
    username = forms.CharField(label='Username', max_length=30)
    mobile_number = forms.CharField(label='Mobile Number', max_length=10)
    email = forms.EmailField(label='Email')
    password1 = forms.CharField(label='Password',widget=forms.PasswordInput())
    password2 = forms.CharField(label='Password (Again)',widget=forms.PasswordInput())

    def clean_password2(self):
        if 'password1' in self.cleaned_data:
            password1 = self.cleaned_data['password1']
            password2 = self.cleaned_data['password2']
            if password1 == password2:
                return password2
        raise forms.ValidationError('Passwords do not match.')

    def clean_username(self):
        username = self.cleaned_data['username']
        if not re.search(r'^\w+$', username):
            raise forms.ValidationError('Username can only contain alphanumeric characters and the underscore.')
        try:
            User.objects.get(username=username)
        except ObjectDoesNotExist:
            return username
        raise forms.ValidationError('Username is already taken.')

    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        self.fields['username'].widget = TextInput(attrs={
            'required':''})
        self.fields['password1'].widget = PasswordInput(attrs={
            'required':''})
        self.fields['password2'].widget = PasswordInput(attrs={
            'required':''})
        self.fields['email'].widget = TextInput(attrs={
            'required':''})

# For account update

class UserForm(forms.ModelForm):
    class Meta:
        model = PgUser
        fields = ['email', 'name']


# Form for new Bill


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ['staff_id','cash_paid']

    def __init__(self, *args, **kwargs):
        super(BillForm, self).__init__(*args, **kwargs)
        self.fields['staff_id'].widget = TextInput(attrs={
            'required':''})
        self.fields['cash_paid'].widget = TextInput(attrs={

            'required':''})


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['itemcode','itemname','quantity','total']

    def __init__(self, *args, **kwargs):
        super(ItemForm, self).__init__(*args, **kwargs)
        self.fields['quantity'].widget.attrs['readonly'] = True
        #self.fields['total'].widget.attrs['readonly'] = True

class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = ['referral_id','customer_id']

    def clean(self):
        cleaned = self.cleaned_data
        refid = self.cleaned_data['referral_id']
        if refid != "":
            try:
                ref = Entry.objects.get(entry_id=refid)
                if ref.use_count > 9:
                    raise forms.ValidationError("Referral limit reached!")
                c_id = self.cleaned_data.get('customer_id')
                c2_id = Entry.objects.get(entry_id=refid).customer_id
                if c_id == c2_id:
                    raise forms.ValidationError("Error! Customer cannot refer himself!")
            except ObjectDoesNotExist:
                pass

        return cleaned

    def __init__(self, *args, **kwargs):
        super(EntryForm, self).__init__(*args, **kwargs)
        #self.fields['customer_id'].widget = TextInput(attrs={
        #    'required':''})



class AssocEntryForm(forms.ModelForm):

    store_name = forms.CharField(label='Store Name', max_length=30)
    category = forms.ModelChoiceField(queryset=AssociateCategory.objects.all(), empty_label=None)
    class Meta:
        model = Entry
        fields = ['referral_id','customer_id','purchase_value']

    def clean(self):
        cleaned = self.cleaned_data
        refid = self.cleaned_data['referral_id']
        if refid != "":
            try:
                ref = Entry.objects.get(entry_id=refid)
                if ref.use_count > 9:
                    raise forms.ValidationError("Referral limit reached!")
                c_id = self.cleaned_data.get('customer_id')
                c2_id = Entry.objects.get(entry_id=refid).customer_id
                if c_id == c2_id:
                    raise forms.ValidationError("Error! Customer cannot refer himself!")
            except ObjectDoesNotExist:
                pass
        store_name = self.cleaned_data['store_name']
        try:
            seller = Associate.objects.get(store_name=store_name)
        except ObjectDoesNotExist:
            raise forms.ValidationError("Error! Invalid Store name!")
        return cleaned

    def __init__(self, *args, **kwargs):
        super(AssocEntryForm, self).__init__(*args, **kwargs)
        self.fields['customer_id'].widget = TextInput(attrs={
            'required':''})
        self.fields['purchase_value'].widget = TextInput(attrs={
            'required':''})
        self.fields['store_name'].widget = TextInput(attrs={
            'required':''})

class ItemcodeForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['itemcode']

class RechargeForm(forms.ModelForm):
    class Meta:
        model = Recharge
        fields = ['number','amount']

    operator = forms.ModelChoiceField(queryset=Operator.objects.all().order_by('name'))

    def __init__(self, *args, **kwargs):
        super(RechargeForm, self).__init__(*args, **kwargs)
        self.fields['number'].widget = TextInput(attrs={
            'required':'','data-a-dec':'.', 'data-a-sep':','})
        self.fields['amount'].widget = TextInput(attrs={
            'required':'','data-a-dec':'.', 'data-a-sep':','})

class BarcodeForm(forms.Form):
    code = forms.CharField(label='Code', max_length=30)


class AdminRechargeForm(forms.ModelForm):
    class Meta:
        model = Recharge
        fields = ['number','amount','customer_id']

    operator = forms.ModelChoiceField(queryset=Operator.objects.all().order_by('name'))

    def __init__(self, *args, **kwargs):
        super(AdminRechargeForm, self).__init__(*args, **kwargs)
        self.fields['number'].widget = TextInput(attrs={
            'required':'','data-a-dec':'.', 'data-a-sep':','})
        self.fields['amount'].widget = TextInput(attrs={
            'required':'','data-a-dec':'.', 'data-a-sep':','})
        self.fields['amount'].widget = TextInput(attrs={
            'required':''})

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['user_id','amount','remarks']

from django.conf.urls import url
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.views import password_change,password_change_done

urlpatterns = [
    url(r'^$', views.index,name='index'),
    url(r'^profile/$',views.profile,name='profile'),
    url(r'^login/$', views.login_page,name='login'),
    url(r'^logout/$', views.logout_page,name='logout'),
    url(r'^account_update/$', views.edit_user,name='account_update'),
    url(r'^message/$',views.message,name='message'),
    url(r'^changepassword/$', password_change,{'template_name': 'common/password_change_form.html'},name="password_change"),
    url(r'^password-change-done/$', password_change_done,{'template_name': 'common/password_change_done.html'},name='password_change_done'),

    url(r'^myaccount/$',views.EntryList.as_view(),name='myaccount'),
    url(r'^entry/(?P<id>\w+)$',views.EntryDetailView.as_view(),name='entry'),
    url(r'^services/recharge$',views.services_recharge,name='recharge'),
    url(r'^services/rechargehistory$',views.services_rechargehistory.as_view(),name='rechargehistory'),

    url(r'^mybills/$',views.BillsList.as_view(),name='franchise_bills'),
    url(r'^bill/(?P<id>\w+)$',views.BillDetailView.as_view(),name='bill'),
    url(r'^mysales/$',views.SalesList.as_view(),name='franchise_sales'),
    url(r'^newbill/$',views.new_bill,name='new_bill'),
    url(r'^assocbill/$',views.assoc_bill,name='assoc_bill'),
    url(r'^newbill/newitem/$',views.new_item,name='new_item'), # AJAX Request
    url(r'^billdetail/$',views.bill_detail,name='bill_detail'),
    url(r'^newbill/newcustomer/$',views.new_customer,name='new_customer'), # AJAX Request
    url(r'^viewstock/$',views.StockList.as_view(),name='view_stock'),
    url(r'^autocomplete_tags/$', views.autocomplete_tags, name='autocomplete_tags'), # AJAX Request
    url(r'^requeststock/stocksearch/$',views.stock_search,name='stock_search'), # AJAX Request
    url(r'^requeststock/$',views.request_stock,name='request_stock'),
    url(r'^requeststock/stockcheckout/$',views.stock_checkout,name='stock_checkout'),
    url(r'^viewrequests/$',views.RequestsView.as_view(),name='view_requests'),
    url(r'^request/(?P<id>\w+)$',views.RequestDetailView.as_view(),name='request_detail'),

    url(r'^staffsales/$',views.StaffSalesList.as_view(),name='staff_sales'),

    url(r'^allrequests/$',views.AllRequestsList.as_view(),name='all_requests'),
    url(r'^allrequests/(?P<id>\w+)$',views.all_requests_detail,name='all_requests_detail'),
    url(r'^allrequests/acceptorder/$',views.ajax_accept_order,name='accept_order'),
    url(r'^allrequests/cancelorder/$',views.ajax_cancel_order,name='cancel_order'),
    url(r'^recharge/$',views.admin_recharge,name='admin_recharge'),
    url(r'^sendemail/$',views.sendemail,name='sendemail'),
    url(r'^sendsms/$',views.sendsms,name='sendsms'),
    url(r'^smsreceiver/$',views.smsreceiver,name='smsreceiver'),

    url(r'^charity/$',views.CharityList.as_view(),name='charity'),
    url(r'^makepayment/$', views.make_payment,name='make_payment'),
    url(r'^termsandconditions/$', views.tncview,name='tncview'),
    url(r'^forgotpassword/$',views.forgot_password,name='forgot_password'),
    url(r'^termsandconditions-fullpage/$', views.tnc_full_view,name='tncfullview'),
    url(r'^privacy-policy/$', views.privacy_policy,name='tncview'),
]

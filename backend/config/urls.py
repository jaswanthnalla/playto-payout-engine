from django.contrib import admin
from django.urls import path
from payouts.views import (
    PayoutRequestView,
    MerchantDashboardView,
    MerchantListView,
    PayoutListView,
    PayoutDetailView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/payouts', PayoutRequestView.as_view(), name='payout-request'),
    path('api/v1/merchants', MerchantListView.as_view(), name='merchant-list'),
    path('api/v1/merchants/<uuid:merchant_id>/dashboard',
         MerchantDashboardView.as_view(), name='merchant-dashboard'),
    path('api/v1/merchants/<uuid:merchant_id>/payouts',
         PayoutListView.as_view(), name='payout-list'),
    path('api/v1/payouts/<uuid:payout_id>',
         PayoutDetailView.as_view(), name='payout-detail'),
]

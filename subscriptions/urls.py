from django.urls import path
from .import views

urlpatterns = [
    path("plans/", views.PlanListCreateView.as_view(), name="plan-list-create"),
    path("plans/<int:pk>/", views.PlanRetrieveUpdateDeleteView.as_view(), name="plan-detail"),

    path("subscriptions/", views.SubscriptionListView.as_view(), name="subscription-list"),
    path("subscriptions/create/", views.SubscriptionCreateView.as_view(), name="subscription-create"),

    path("subscriptions/checkout/", views.create_checkout_session, name="stripe-checkout"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe-webhook"),
    
    path("success/", views.success, name="payment-success"),
    path("cancel/", views.cancel, name="payment-cancel"),

    # admin dashyboard
    path("admin/dashboard-stats/", views.AdminDashboardStatsView.as_view()),
    path("admin/plans/<int:pk>/delete/", views.AdminPlanDeleteView.as_view()),
    path("admin/subscriptions/<int:subscription_id>/delete/",views.AdminSubscriptionDeleteView.as_view(),name="admin-subscription-delete"),
        
    # path("admin/subscriptions/<int:pk>/extend/", views.ExtendSubscriptionView.as_view()),
    path("admin/subscriptions/",views.SubscriptionListAPIView.as_view(),name="admin-subscriptions"),
    path("confirm-subscription/", views.confirm_subscription, name="confirm-subscription"),
    path("admin/subscriptions/<int:pk>/extend/",views.ExtendSubscriptionView.as_view(),name="extend-subscription"),
    path("subscription/cancel/<int:subscription_id>/",views.CancelOwnSubscriptionAPIView.as_view(), name="cancel-subscription"),
    path("my-subscriptions/",views.MySubscriptionAPIView.as_view(),name="my-subscriptions"),
    
    path("subscriptions/toggle-auto-renew/<int:subscription_id>/",views.ToggleAutoRenewAPIView.as_view(),name="toggle-auto-renew" ),
    path('admin/subscriptions/ratio/',views. SubscriptionRatioAPIView.as_view(), name='admin-subscription-ratio'),
    path("subscription/upgrade/", views.UpgradePlanAPIView.as_view(), name="upgrade-plan"),
    path('admin/subscription/<int:subscription_id>/pause/',views. AdminPauseSubscriptionAPIView.as_view(), name='admin-pause-subscription'),

    path("admin/subscription-users/",views.AdminAllSubscriptionUsersBillingView.as_view(),name="admin-all-subscription-users-billing"),
    path(
        "admin/users/<int:user_id>/billing-summary/",
        views.AdminUserBillingSummaryView.as_view(),
        name="admin-user-billing-summary"
    ),
    path(
        "admin/subscriptions/landscaper/<int:user_id>/",
        views.AdminLandscaperSubscriptionManageAPIView.as_view(),
        name="admin-landscaper-subscription-manage",
    ),
    path(
        "admin/subscriptions/<int:subscription_id>/action/",
        views.AdminSubscriptionActionAPIView.as_view(),
        name="admin-subscription-action"
    ),
    path(
        "admin/subscriptions/assign/",
        views.AdminAssignSubscriptionAPIView.as_view(),
        name="admin-assign-subscription"
    ),
    path(
        "admin/users/<int:user_id>/billing-history/",
        views.AdminUserBillingHistoryAPIView.as_view(),
        name="admin-user-billing-history"
    ),
    path(
        "admin/revenue-breakdown/",
        views.AdminRevenueBreakdownAPIView.as_view(),
        name="admin-revenue-breakdown",
    ),
    # apple verification 
    path(
        "subscriptions/apple-verify/",
        views.AppleVerifySubscriptionAPIView.as_view(),
        name="apple-verify-subscription"
    ),
    path(
        "webhooks/apple-iap/",
        views.apple_iap_webhook,
        name="apple-iap-webhook"
    ),


]


from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from strawberry.django.views import GraphQLView

from backend.tunisovereign_core.schema_graphql import schema

from backend.tunisovereign_core.api_rest import (
    RegisterView,
    SovereignTokenObtainPairView,
    PharmaFacilityViewSet,
    MedicineViewSet,
    MedicineBatchViewSet,
    ShipmentViewSet,
    ColdChainReadingViewSet,
    ColdChainSensorViewSet,
    BatchScanViewSet,
    PharmaAnomalyViewSet,
    DrugAuthenticityReceiptViewSet,
)

router = DefaultRouter()

router.register("facilities", PharmaFacilityViewSet)
router.register("medicines", MedicineViewSet)
router.register("batches", MedicineBatchViewSet)
router.register("shipments", ShipmentViewSet)
router.register("cold-chain-readings", ColdChainReadingViewSet)
router.register("cold-chain-sensors", ColdChainSensorViewSet)
router.register("batch-scans", BatchScanViewSet)
router.register("anomalies", PharmaAnomalyViewSet)
router.register("zk-receipts", DrugAuthenticityReceiptViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("graphql/", GraphQLView.as_view(schema=schema), name="graphql"),

    path("api/auth/register/", RegisterView.as_view(), name="register"),
    path("api/auth/login/", SovereignTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    path("api/v1/", include(router.urls)),
]

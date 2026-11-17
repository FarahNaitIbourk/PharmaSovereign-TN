
from rest_framework import serializers, viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from backend.tunisovereign_core.models import (
    StakeholderUser,
    PharmaFacility,
    Medicine,
    MedicineBatch,
    Shipment,
    ColdChainSensor,
    ColdChainReading,
    BatchScan,
    PharmaAnomaly,
    DrugAuthenticityReceipt,
)


# -------------------------
# AUTHENTIFICATION
# -------------------------

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = StakeholderUser
        fields = [
            "id", "username", "password", "email",
            "first_name", "last_name", "governorate",
            "preferred_dialect",
        ]

    def create(self, validated_data):
        return StakeholderUser.objects.create_user(
            **validated_data,
            role=StakeholderUser.Role.COOP_MEMBER,
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response(
            {
                "message": "Compte créé avec succès.",
                "user_id": user.id,
                "username": user.username,
                "role": user.role,
            },
            status=status.HTTP_201_CREATED,
        )


class SovereignTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["governorate"] = user.governorate
        token["wallet_address"] = user.wallet_address or ""
        token["preferred_dialect"] = user.preferred_dialect
        return token


class SovereignTokenObtainPairView(TokenObtainPairView):
    serializer_class = SovereignTokenObtainPairSerializer


# -------------------------
# PERMISSIONS
# -------------------------



class PharmaRolePermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        role = request.user.role

        # Consultation autorisée aux quatre rôles.
        if request.method in permissions.SAFE_METHODS:
            return role in [
                StakeholderUser.Role.COOP_MEMBER,
                StakeholderUser.Role.REGIONAL_AUDITOR,
                StakeholderUser.Role.NATIONAL_ADMIN,
                StakeholderUser.Role.AGENT_SERVICE,
            ]

        # Seuls ces rôles peuvent effectuer des écritures.
        if request.method == "DELETE":
            return role == StakeholderUser.Role.NATIONAL_ADMIN

        return role in [
            StakeholderUser.Role.REGIONAL_AUDITOR,
            StakeholderUser.Role.NATIONAL_ADMIN,
            StakeholderUser.Role.AGENT_SERVICE,
        ]

    def has_object_permission(self, request, view, obj):
        role = request.user.role

        # L'administrateur national possède un accès complet.
        if role == StakeholderUser.Role.NATIONAL_ADMIN:
            return True

        # Les suppressions sont réservées à l'administrateur national.
        if request.method == "DELETE":
            return False

        # Les utilisateurs régionaux sont limités à leur gouvernorat.
        if role in [
            StakeholderUser.Role.COOP_MEMBER,
            StakeholderUser.Role.REGIONAL_AUDITOR,
        ]:
            governorate = self.get_object_governorate(obj)

            # Les objets sans gouvernorat (ex. médicament)
            # sont des ressources nationales communes.
            if governorate is None:
                return True

            return governorate == request.user.governorate

        return True

    @staticmethod
    def get_object_governorate(obj):
        if hasattr(obj, "governorate"):
            return obj.governorate

        if hasattr(obj, "assigned_governorate"):
            return obj.assigned_governorate

        if hasattr(obj, "facility"):
            return obj.facility.governorate

        if hasattr(obj, "destination"):
            return obj.destination.governorate

        if hasattr(obj, "shipment"):
            return PharmaRolePermission.get_object_governorate(
                obj.shipment
            )

        if hasattr(obj, "batch"):
            return PharmaRolePermission.get_object_governorate(
                obj.batch
            )

        return None
    
    def filter_queryset(self, request, queryset, view):
        role = request.user.role

        # Administrateur et agent technique : accès national.
        if role in [
            StakeholderUser.Role.NATIONAL_ADMIN,
            StakeholderUser.Role.AGENT_SERVICE,
        ]:
            return queryset

        model = queryset.model

        # Ressources nationales communes.
        if model == Medicine:
            return queryset

        if model == PharmaFacility:
            return queryset.filter(
                governorate=request.user.governorate
            )

        if model == MedicineBatch:
            return queryset.filter(
                assigned_governorate=request.user.governorate
            )

        if model == Shipment:
            return queryset.filter(
                batch__assigned_governorate=request.user.governorate
            )

        if model == BatchScan:
            return queryset.filter(
                batch__assigned_governorate=request.user.governorate
            )

        if model == ColdChainSensor:
            return queryset.filter(
                shipment__batch__assigned_governorate=request.user.governorate
            )

        if model == ColdChainReading:
            return queryset.filter(
                shipment__batch__assigned_governorate=request.user.governorate
            )

        if model == PharmaAnomaly:
            return queryset.filter(
                batch__assigned_governorate=request.user.governorate
            )

        if model == DrugAuthenticityReceipt:
            return queryset.filter(
                batch__assigned_governorate=request.user.governorate
            )

        return queryset.none()



# -------------------------
# SERIALIZERS PHARMACEUTIQUES
# -------------------------

class PharmaFacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmaFacility
        fields = "__all__"


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = "__all__"


class MedicineBatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicineBatch
        fields = "__all__"


class ShipmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = "__all__"


class ColdChainSensorSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColdChainSensor
        fields = "__all__"


class ColdChainReadingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColdChainReading
        fields = "__all__"


class BatchScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = BatchScan
        fields = "__all__"
        read_only_fields = ["scanned_by", "scanned_at", "is_authorized"]


class PharmaAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        model = PharmaAnomaly
        fields = "__all__"


class DrugAuthenticityReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = DrugAuthenticityReceipt
        fields = "__all__"


# -------------------------
# VIEWSETS REST
# -------------------------


class PharmaFacilityViewSet(viewsets.ModelViewSet):
    queryset = PharmaFacility.objects.all().order_by("name")
    serializer_class = PharmaFacilitySerializer
    permission_classes = [PharmaRolePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.permission_classes[0]().filter_queryset(
            self.request, queryset, self
        )

class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all().order_by("name")
    serializer_class = MedicineSerializer
    permission_classes = [PharmaRolePermission]

class MedicineBatchViewSet(viewsets.ModelViewSet):
    queryset = MedicineBatch.objects.select_related("medicine").all()
    serializer_class = MedicineBatchSerializer
    permission_classes = [PharmaRolePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.permission_classes[0]().filter_queryset(
            self.request, queryset, self
        )
    
class ShipmentViewSet(viewsets.ModelViewSet):
    queryset = Shipment.objects.select_related(
        "batch", "origin", "destination"
    ).all().order_by("-created_at")
    serializer_class = ShipmentSerializer
    permission_classes = [PharmaRolePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.permission_classes[0]().filter_queryset(
            self.request, queryset, self
        )
    

class ColdChainSensorViewSet(viewsets.ModelViewSet):
    queryset = ColdChainSensor.objects.select_related("shipment").all()
    serializer_class = ColdChainSensorSerializer
    permission_classes = [PharmaRolePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.permission_classes[0]().filter_queryset(
            self.request, queryset, self
        )

    


class ColdChainReadingViewSet(viewsets.ModelViewSet):
    queryset = ColdChainReading.objects.select_related(
        "sensor", "shipment"
    ).all().order_by("-recorded_at")
    serializer_class = ColdChainReadingSerializer
    permission_classes = [PharmaRolePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.permission_classes[0]().filter_queryset(
            self.request, queryset, self
        )


class BatchScanViewSet(viewsets.ModelViewSet):
    queryset = BatchScan.objects.select_related(
        "batch", "facility", "scanned_by"
    ).all()
    serializer_class = BatchScanSerializer
    permission_classes = [PharmaRolePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.permission_classes[0]().filter_queryset(
            self.request, queryset, self
        )

    def perform_create(self, serializer):
        batch = serializer.validated_data["batch"]
        facility = serializer.validated_data["facility"]

        authorized = (
            batch.assigned_governorate == facility.governorate
        )

        serializer.save(
            scanned_by=self.request.user,
            is_authorized=authorized
        )

class PharmaAnomalyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PharmaAnomaly.objects.select_related(
        "batch", "shipment", "reading"
    ).all().order_by("-detected_at")
    serializer_class = PharmaAnomalySerializer
    permission_classes = [PharmaRolePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.permission_classes[0]().filter_queryset(
            self.request, queryset, self
        )
class DrugAuthenticityReceiptViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DrugAuthenticityReceipt.objects.select_related(
        "batch", "agent_execution"
    ).all().order_by("-created_at")
    serializer_class = DrugAuthenticityReceiptSerializer
    permission_classes = [PharmaRolePermission]

    def get_queryset(self):
        queryset = super().get_queryset()
        return self.permission_classes[0]().filter_queryset(
            self.request, queryset, self
        )

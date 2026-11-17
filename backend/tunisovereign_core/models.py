from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db.models import Q


class StakeholderUser(AbstractUser):
    class Role(models.TextChoices):
        COOP_MEMBER = "COOP_MEMBER", "Farmer / Citizen / Field Operator"
        REGIONAL_AUDITOR = "REGIONAL_AUDITOR", "Regional GDA / PCT / Municipal Auditor"
        NATIONAL_ADMIN = "NATIONAL_ADMIN", "Governorate / National Ministry Admin"
        AGENT_SERVICE = "AGENT_SERVICE", "Autonomous AI Agent & MCP Service Account"

    role = models.CharField(max_length=24, choices=Role.choices, default=Role.COOP_MEMBER)
    governorate = models.CharField(max_length=64, db_index=True, default="Kasserine")
    wallet_address = models.CharField(max_length=42, blank=True, null=True)
    preferred_dialect = models.CharField(max_length=16, default="ar-TN")


class CooperativeUnit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    governorate = models.CharField(max_length=64, db_index=True)
    track_domain = models.CharField(max_length=64, default="Track_01_Water_Agri")
    daily_quota_limit = models.FloatField(help_text="Max daily resource/water/medicine quota")
    contract_address = models.CharField(max_length=42, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ResourceNodePlot(models.Model):
    coop = models.ForeignKey(CooperativeUnit, on_delete=models.CASCADE, related_name="nodes")
    owner = models.ForeignKey(StakeholderUser, on_delete=models.CASCADE, related_name="owned_nodes")
    node_code = models.CharField(max_length=32, unique=True)
    crop_or_sector_type = models.CharField(max_length=64)
    allocated_share_pct = models.FloatField(default=10.0)
    is_valve_or_dispatch_active = models.BooleanField(default=False)


class TelemetryReading(models.Model):
    class MetricType(models.TextChoices):
        SOIL_MOISTURE = "MOISTURE", "Soil Moisture (%)"
        AQUIFER_FLOW = "FLOW", "Flow / Dispensation Rate (L/min or Units/h)"
        TEMPERATURE = "TEMP", "Ambient / Cold-Chain Temperature (C)"
        PRESSURE_OR_STOCK = "STOCK", "Piezo Pressure / Inventory Level"

    node = models.ForeignKey(ResourceNodePlot, on_delete=models.CASCADE, related_name="readings")
    timestamp = models.DateTimeField(db_index=True)
    metric_type = models.CharField(max_length=16, choices=MetricType.choices)
    value = models.FloatField()
    ingestion_protocol = models.CharField(max_length=16, default="gRPC")

    class Meta:
        indexes = [models.Index(fields=["node", "metric_type", "-timestamp"])]


class AnomalyAndForecastEvent(models.Model):
    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        CRITICAL = "CRITICAL", "Critical Breach / Leak / Diversion"

    node = models.ForeignKey(ResourceNodePlot, on_delete=models.CASCADE, related_name="anomalies")
    detected_at = models.DateTimeField(auto_now_add=True)
    anomaly_type = models.CharField(max_length=64)
    severity = models.CharField(max_length=16, choices=Severity.choices)
    isolation_forest_score = models.FloatField()
    forecasted_deficit_24h = models.FloatField(default=0.0)


class AgentLoopExecution(models.Model):
    thread_id = models.CharField(max_length=64, db_index=True)
    trigger_source = models.CharField(max_length=64)
    darja_transcript = models.TextField(blank=True)
    parsed_intent_json = models.JSONField(default=dict)
    mcp_tools_invoked = models.JSONField(default=list)
    skills_executed = models.JSONField(default=list)
    final_recommendation = models.TextField()
    confidence_score = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)


class OnChainZKReceipt(models.Model):
    agent_execution = models.OneToOneField(AgentLoopExecution, on_delete=models.CASCADE, related_name="zk_receipt")
    zk_commitment_hash = models.CharField(max_length=66, unique=True)
    public_inputs_json = models.JSONField(default=dict)
    tx_hash = models.CharField(max_length=66, unique=True)
    block_number = models.PositiveIntegerField()
    network_name = models.CharField(max_length=32, default="Foundry-Anvil-Local")
    is_verified_on_chain = models.BooleanField(default=True)

# ============================================================
# PHARMASOVEREIGN-TN - PHARMACEUTICAL DOMAIN MODELS
# ============================================================


class PharmaFacility(models.Model):
    """
    Pharmaceutical facilities:
    PCT depots, warehouses, pharmacies and hospitals.
    """

    class FacilityType(models.TextChoices):
        PCT_DEPOT = "PCT_DEPOT", "PCT Depot"
        WAREHOUSE = "WAREHOUSE", "Warehouse"
        PHARMACY = "PHARMACY", "Pharmacy"
        HOSPITAL = "HOSPITAL", "Hospital"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    facility_type = models.CharField(
        max_length=20,
        choices=FacilityType.choices
    )
    governorate = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["governorate", "name"]

    def __str__(self):
        return f"{self.name} - {self.governorate}"


class Medicine(models.Model):
    """
    Pharmaceutical product and its storage requirements.
    Temperature limits are configurable per medicine.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product_code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=200)
    active_ingredient = models.CharField(max_length=200, blank=True)
    manufacturer = models.CharField(max_length=200)

    cold_chain_required = models.BooleanField(default=True)
    min_storage_temp_c = models.FloatField(
        default=2.0,
        validators=[MinValueValidator(-100), MaxValueValidator(100)]
    )
    max_storage_temp_c = models.FloatField(
        default=8.0,
        validators=[MinValueValidator(-100), MaxValueValidator(100)]
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(max_storage_temp_c__gte=models.F("min_storage_temp_c")),
                name="medicine_valid_temperature_range"
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.product_code})"


class MedicineBatch(models.Model):
    """
    A manufactured batch of a pharmaceutical product.
    """

    class AuthenticityStatus(models.TextChoices):
        PENDING = "PENDING", "Pending verification"
        VERIFIED = "VERIFIED", "Verified"
        SUSPICIOUS = "SUSPICIOUS", "Suspicious"
        COUNTERFEIT = "COUNTERFEIT", "Counterfeit"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    medicine = models.ForeignKey(
        Medicine,
        on_delete=models.PROTECT,
        related_name="batches"
    )

    batch_number = models.CharField(max_length=100, unique=True)
    serial_number = models.CharField(
        max_length=150,
        unique=True,
        null=True,
        blank=True
    )
    manufacturing_date = models.DateField()
    expiry_date = models.DateField()

    assigned_governorate = models.CharField(max_length=100)
    authenticity_status = models.CharField(
        max_length=20,
        choices=AuthenticityStatus.choices,
        default=AuthenticityStatus.PENDING
    )

    quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-manufacturing_date"]
        constraints = [
            models.CheckConstraint(
                condition=Q(expiry_date__gte=models.F("manufacturing_date")),
                name="batch_expiry_after_manufacturing"
            )
        ]

    def __str__(self):
        return f"{self.batch_number} - {self.medicine.name}"


class Shipment(models.Model):
    """
    Tracks the movement of one medicine batch
    between two pharmaceutical facilities.
    """

    class ShipmentStatus(models.TextChoices):
        PREPARING = "PREPARING", "Preparing"
        IN_TRANSIT = "IN_TRANSIT", "In transit"
        DELIVERED = "DELIVERED", "Delivered"
        BLOCKED = "BLOCKED", "Blocked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tracking_code = models.CharField(max_length=100, unique=True)

    batch = models.ForeignKey(
        MedicineBatch,
        on_delete=models.PROTECT,
        related_name="shipments"
    )

    origin = models.ForeignKey(
        PharmaFacility,
        on_delete=models.PROTECT,
        related_name="outgoing_shipments"
    )

    destination = models.ForeignKey(
        PharmaFacility,
        on_delete=models.PROTECT,
        related_name="incoming_shipments"
    )

    status = models.CharField(
        max_length=20,
        choices=ShipmentStatus.choices,
        default=ShipmentStatus.PREPARING
    )

    shipped_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.tracking_code


class ColdChainSensor(models.Model):
    """
    IoT sensor assigned to a pharmaceutical shipment.
    """

    class SensorType(models.TextChoices):
        TEMPERATURE = "TEMPERATURE", "Temperature"
        TEMPERATURE_HUMIDITY = "TEMP_HUMIDITY", "Temperature and humidity"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sensor_code = models.CharField(max_length=100, unique=True)
    sensor_type = models.CharField(
        max_length=20,
        choices=SensorType.choices,
        default=SensorType.TEMPERATURE
    )

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sensors"
    )

    is_active = models.BooleanField(default=True)
    installed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.sensor_code


class ColdChainReading(models.Model):
    """
    Time-stamped telemetry received from cold-chain sensors.
    """

    class IngestionProtocol(models.TextChoices):
        GRPC = "gRPC", "gRPC"
        REST = "REST", "REST"
        MQTT = "MQTT", "MQTT"
        SIMULATOR = "SIMULATOR", "Simulator"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sensor = models.ForeignKey(
        ColdChainSensor,
        on_delete=models.PROTECT,
        related_name="readings"
    )

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.PROTECT,
        related_name="temperature_readings"
    )

    recorded_at = models.DateTimeField()
    temperature_c = models.FloatField()
    humidity_pct = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    signature_hmac = models.CharField(max_length=256)
    ingestion_protocol = models.CharField(
        max_length=20,
        choices=IngestionProtocol.choices,
        default=IngestionProtocol.GRPC
    )

    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["shipment", "recorded_at"]),
            models.Index(fields=["sensor", "recorded_at"]),
        ]

    def __str__(self):
        return f"{self.sensor.sensor_code} - {self.temperature_c}°C"


class BatchScan(models.Model):
    """
    Records every scan of a medicine batch.
    Used to detect unauthorized geographic distribution.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    batch = models.ForeignKey(
        MedicineBatch,
        on_delete=models.PROTECT,
        related_name="scans"
    )

    facility = models.ForeignKey(
        PharmaFacility,
        on_delete=models.PROTECT,
        related_name="batch_scans"
    )

    scanned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pharmaceutical_scans"
    )

    scanned_at = models.DateTimeField(auto_now_add=True)
    scan_reference = models.CharField(max_length=150, blank=True)
    is_authorized = models.BooleanField(default=True)

    class Meta:
        ordering = ["-scanned_at"]
        indexes = [
            models.Index(fields=["batch", "scanned_at"]),
            models.Index(fields=["facility", "scanned_at"]),
        ]

    def __str__(self):
        return f"Scan {self.batch.batch_number} at {self.facility.name}"


class PharmaAnomaly(models.Model):
    """
    Cold-chain, anti-leakage and authenticity alerts.
    """

    class AnomalyType(models.TextChoices):
        TEMPERATURE_EXCURSION = "TEMP_EXCURSION", "Temperature excursion"
        GOVERNORATE_MISMATCH = "GOV_MISMATCH", "Unauthorized governorate"
        SUSPICIOUS_SCAN = "SUSPICIOUS_SCAN", "Suspicious batch scan"
        SENSOR_TAMPERING = "SENSOR_TAMPERING", "Sensor tampering"
        AUTHENTICITY_RISK = "AUTH_RISK", "Authenticity risk"

    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    batch = models.ForeignKey(
        MedicineBatch,
        on_delete=models.PROTECT,
        related_name="anomalies"
    )

    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anomalies"
    )

    reading = models.ForeignKey(
        ColdChainReading,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="anomalies"
    )

    anomaly_type = models.CharField(
        max_length=30,
        choices=AnomalyType.choices
    )

    severity = models.CharField(
        max_length=10,
        choices=Severity.choices,
        default=Severity.MEDIUM
    )

    description = models.TextField()
    detection_score = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(1)]
    )

    detected_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-detected_at"]
        indexes = [
            models.Index(fields=["anomaly_type", "severity"]),
            models.Index(fields=["batch", "detected_at"]),
        ]

    def __str__(self):
        return f"{self.anomaly_type} - {self.batch.batch_number}"


class DrugAuthenticityReceipt(models.Model):
    """
    Stores the traceability commitment and blockchain anchoring result.
    A commitment hash is not, by itself, proof of a valid ZK proof.
    """

    class VerificationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        VERIFIED = "VERIFIED", "Verified"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    batch = models.ForeignKey(
        MedicineBatch,
        on_delete=models.PROTECT,
        related_name="authenticity_receipts"
    )

    agent_execution = models.ForeignKey(
        "AgentLoopExecution",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drug_authenticity_receipts"
    )

    commitment_hash = models.CharField(max_length=128, unique=True)
    public_inputs_json = models.JSONField(default=dict, blank=True)

    transaction_hash = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    network_name = models.CharField(
        max_length=100,
        default="Foundry-Anvil-Local"
    )

    verification_status = models.CharField(
        max_length=10,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Authenticity receipt - {self.batch.batch_number}"

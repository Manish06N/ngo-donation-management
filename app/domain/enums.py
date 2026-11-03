from enum import Enum


class Role(str, Enum):
    SUPER_ADMIN = "super_admin"
    NGO_MANAGER = "ngo_manager"
    FINANCE_OFFICER = "finance_officer"
    VOLUNTEER_COORDINATOR = "volunteer_coordinator"
    VOLUNTEER = "volunteer"
    DONOR = "donor"


class DonorType(str, Enum):
    INDIVIDUAL = "individual"
    ORGANIZATION = "organization"


class DonorStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class CampaignCategory(str, Enum):
    EDUCATION = "education"
    HEALTH = "health"
    DISASTER_RELIEF = "disaster_relief"
    ENVIRONMENT = "environment"
    LIVELIHOOD = "livelihood"
    COMMUNITY = "community"
    OTHER = "other"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class DonationMethod(str, Enum):
    CASH = "cash"
    BANK_TRANSFER = "bank_transfer"
    UPI = "upi"
    CARD = "card"
    CHEQUE = "cheque"
    ONLINE = "online"


class DonationStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    REVERSED = "reversed"
    REFUNDED = "refunded"


class ReceiptStatus(str, Enum):
    ISSUED = "issued"
    VOID = "void"


class VolunteerStatus(str, Enum):
    APPLIED = "applied"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class AssignmentStatus(str, Enum):
    ASSIGNED = "assigned"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AttendanceStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"


class ProjectStatus(str, Enum):
    PLANNING = "planning"
    APPROVED = "approved"
    ACTIVE = "active"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ApprovalState(str, Enum):
    NOT_SUBMITTED = "not_submitted"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ApprovalAction(str, Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"


class MilestoneStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExpenseCategory(str, Enum):
    TRAVEL = "travel"
    SUPPLIES = "supplies"
    LOGISTICS = "logistics"
    VENUE = "venue"
    PROFESSIONAL_SERVICES = "professional_services"
    UTILITIES = "utilities"
    FOOD = "food"
    MEDICAL = "medical"
    ADMINISTRATION = "administration"
    OTHER = "other"


class ExpenseStatus(str, Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REIMBURSED = "reimbursed"


class ResourceCategory(str, Enum):
    FOOD_PACKAGES = "food_packages"
    CLOTHING = "clothing"
    EDUCATIONAL_MATERIALS = "educational_materials"
    MEDICAL_SUPPLIES = "medical_supplies"
    EMERGENCY_KITS = "emergency_kits"
    OTHER = "other"


class MovementType(str, Enum):
    STOCK_IN = "stock_in"
    STOCK_OUT = "stock_out"
    ALLOCATION = "allocation"


class BeneficiaryCategory(str, Enum):
    CHILD = "child"
    ADULT = "adult"
    ELDERLY = "elderly"
    FAMILY = "family"
    COMMUNITY_GROUP = "community_group"
    OTHER = "other"


class NotificationCategory(str, Enum):
    ASSIGNMENT = "assignment"
    APPROVAL = "approval"
    DEADLINE = "deadline"
    OVERDUE = "overdue"
    LOW_STOCK = "low_stock"
    EXPENSE = "expense"
    CAMPAIGN = "campaign"
    BUDGET = "budget"
    IMPACT = "impact"
    SYSTEM = "system"

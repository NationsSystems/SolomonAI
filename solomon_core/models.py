# -------------------------------------------------------------------
# FILE: models.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# SQLAlchemy ORM models for the merged SolomonV3 database.
# -------------------------------------------------------------------

from datetime import datetime, timezone
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from solomon_core.db import Base


def utc_now() -> datetime:
    """Return the canonical database timestamp as timezone-aware UTC."""

    return datetime.now(timezone.utc)


def new_opaque_id() -> str:
    """Return a stable opaque identifier for externally referenced records."""

    return uuid.uuid4().hex


GROUP_LIBRARY_SCOPE = "group_library"
GROUP_CONTROLLED_CUSTODY_MODE = "group_controlled"
GROUP_FILE_PERMISSION_POLICY_VERSION = "group_file_permissions_v1"
GROUP_MEMBERSHIP_INVITATION_CONTRACT = "group_membership_invitation_v1"
ORGANIZATION_INVITATION_INTENT_CONTRACT = "organization_invitation_intent_v1"
GROUP_AUDIT_EVENT_CONTRACT = "group_audit_event_v1"
GROUP_FILE_ACCESS_GRANT_TYPE = "group"
WORKSPACE_FOLDER_CONTRACT = "workspace_folder_v1"
WORKSPACE_FOLDER_ROOT_PARENT_KEY = "root"
WORKSPACE_FOLDER_OWNER_SCOPE = "owner"
WORKSPACE_FOLDER_PERMISSION_POLICY_VERSION = "workspace_folder_permissions_v1"
FOLDER_ACCESS_GRANT_TYPE = "direct_user"
FOLDER_GROUP_ACCESS_GRANT_TYPE = "group"
WORKSPACE_INTELLIGENCE_OBJECT_CONTRACT = "workspace_intelligence_object_v1"
WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT = "workspace_intelligence_chunk_v1"
WORKSPACE_INTELLIGENCE_FACT_CONTRACT = "workspace_intelligence_fact_v1"
WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT = "workspace_embedding_reference_v1"
INTELLIGENCE_JOB_CONTRACT = "solomon_intelligence_job_v1"
INTELLIGENCE_JOB_EVENT_CONTRACT = "solomon_intelligence_job_event_v1"
INTELLIGENCE_COMPUTE_EVENT_CONTRACT = "solomon_intelligence_compute_event_v1"
INTELLIGENCE_COMPUTE_REQUEST_EVENT_CONTRACT = "solomon_intelligence_compute_request_event_v1"
INTELLIGENCE_REQUEST_ATTRIBUTION_CONTRACT = "solomon_intelligence_request_attribution_v1"
INTELLIGENCE_CAPACITY_SNAPSHOT_CONTRACT = "solomon_intelligence_capacity_snapshot_v1"
INTELLIGENCE_CAPACITY_ROLLUP_CONTRACT = "solomon_intelligence_capacity_rollup_v1"
INTELLIGENCE_SERVICE_EVENT_CONTRACT = "solomon_intelligence_service_event_v1"
SOLOMON_ACTION_RESULT_CONTRACT = "solomon_action_result_v1"
SOLOMON_ACTION_RESULT_RESOURCE_CONTRACT = "solomon_action_result_resource_v1"
SOLOMON_ACTION_APPLICABILITY_PROFILE_CONTRACT = "solomon_action_applicability_profile_v1"
SOLOMON_ACTION_RESULT_STATUS_READY = "ready"
INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND = "background"
INTELLIGENCE_JOB_STATUS_PENDING = "pending"
INTELLIGENCE_JOB_STATUS_CLAIMED = "claimed"
INTELLIGENCE_JOB_STATUS_RUNNING = "running"
INTELLIGENCE_JOB_STATUS_RETRY_WAIT = "retry_wait"
INTELLIGENCE_JOB_STATUS_SUCCEEDED = "succeeded"
INTELLIGENCE_JOB_STATUS_FAILED = "failed"
INTELLIGENCE_JOB_STATUS_CANCELLED = "cancelled"
INTELLIGENCE_JOB_STATUS_SUPERSEDED = "superseded"
WORKSPACE_INTELLIGENCE_SUPPORTED_OBJECT_TYPES = (
    "file",
    "conversation",
    "person",
    "group",
)


# ===============================================================
# USER / GROUP SHELL
# ===============================================================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    # Password is one optional authentication method. Provider-only users may
    # have no password credential while still owning the same Solomon identity.
    password_hash = Column(String(255), nullable=True)

    role = Column(String(32), default="user", nullable=False, index=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    last_login_at = Column(DateTime(timezone=True), nullable=True)

    must_change_password = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    temp_password_issued_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_login_ip = Column(String(45), nullable=True)
    last_login_ip_version = Column(String(8), nullable=True)
    last_login_ip_country = Column(String(2), nullable=True)
    last_login_ip_region = Column(String(64), nullable=True)
    last_login_ip_city = Column(String(64), nullable=True)
    last_login_ip_source = Column(String(16), nullable=True)

    plan_status = Column(
        String(32),
        default="free",
        nullable=False,
        index=True,
    )
    stripe_customer_id = Column(
        String(255),
        unique=True,
        nullable=True,
    )
    stripe_subscription_id = Column(
        String(255),
        unique=True,
        nullable=True,
    )
    trial_started_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    trial_ends_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_period_end = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    review_limit = Column(Integer, nullable=True)
    reviews_used = Column(Integer, default=0, nullable=False)
    billing_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    external_identities = relationship(
        "ExternalIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="ExternalIdentity.user_id",
    )

    files = relationship(
        "FileRegistry",
        back_populates="uploader",
        cascade="all, delete-orphan",
        foreign_keys="FileRegistry.uploader_id",
    )

    workspace_folders = relationship(
        "WorkspaceFolder",
        back_populates="owner_user",
        cascade="all, delete-orphan",
        foreign_keys="WorkspaceFolder.user_id",
    )

    organizations_created = relationship(
        "Organization",
        back_populates="created_by",
        foreign_keys="Organization.created_by_user_id",
    )

    organization_memberships = relationship(
        "OrganizationMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="OrganizationMembership.user_id",
    )

    organization_groups_created = relationship(
        "OrganizationGroup",
        back_populates="created_by",
        foreign_keys="OrganizationGroup.created_by_user_id",
    )

    organization_group_memberships = relationship(
        "OrganizationGroupMembership",
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="OrganizationGroupMembership.user_id",
    )

    organization_group_memberships_added = relationship(
        "OrganizationGroupMembership",
        back_populates="added_by_user",
        foreign_keys="OrganizationGroupMembership.added_by_user_id",
    )

    received_file_grants = relationship(
        "FileAccessGrant",
        back_populates="granted_to_user",
        cascade="all, delete-orphan",
        foreign_keys="FileAccessGrant.granted_to_user_id",
    )

    issued_file_grants = relationship(
        "FileAccessGrant",
        back_populates="granted_by_user",
        foreign_keys="FileAccessGrant.granted_by_user_id",
    )

    revoked_file_grants = relationship(
        "FileAccessGrant",
        back_populates="revoked_by_user",
        foreign_keys="FileAccessGrant.revoked_by_user_id",
    )

    issued_group_file_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="granted_by_user",
        foreign_keys="FileGroupAccessGrant.granted_by_user_id",
    )

    revoked_group_file_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="revoked_by_user",
        foreign_keys="FileGroupAccessGrant.revoked_by_user_id",
    )

    file_authorization_decisions = relationship(
        "FileAuthorizationDecision",
        back_populates="actor_user",
        foreign_keys="FileAuthorizationDecision.actor_user_id",
    )

    bid_review_records = relationship(
        "BidReviewRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    workspace_artifacts = relationship(
        "WorkspaceArtifact",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    review_sets = relationship(
        "ReviewSet",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    solomon_ai_conversations = relationship(
        "SolomonAIConversation",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    issued_organization_invitations = relationship(
        "OrganizationInvitation",
        back_populates="invited_by_user",
        foreign_keys="OrganizationInvitation.invited_by_user_id",
    )

    accepted_organization_invitations = relationship(
        "OrganizationInvitation",
        back_populates="accepted_by_user",
        foreign_keys="OrganizationInvitation.accepted_by_user_id",
    )

    revoked_organization_invitations = relationship(
        "OrganizationInvitation",
        back_populates="revoked_by_user",
        foreign_keys="OrganizationInvitation.revoked_by_user_id",
    )

    organization_audit_events_as_actor = relationship(
        "OrganizationAuditEvent",
        back_populates="actor_user",
        foreign_keys="OrganizationAuditEvent.actor_user_id",
    )

    organization_audit_events_as_target = relationship(
        "OrganizationAuditEvent",
        back_populates="target_user",
        foreign_keys="OrganizationAuditEvent.target_user_id",
    )

    workspace_intelligence_objects = relationship(
        "WorkspaceIntelligenceObject",
        back_populates="owner_user",
        cascade="all, delete-orphan",
        foreign_keys="WorkspaceIntelligenceObject.user_id",
    )

    workspace_intelligence_subject_objects = relationship(
        "WorkspaceIntelligenceObject",
        back_populates="subject_user",
        foreign_keys="WorkspaceIntelligenceObject.subject_user_id",
    )


class ExternalIdentity(Base):
    """Verified external authentication identity attached to one Solomon user.

    The provider subject is authentication provenance only. Organization, Group,
    file, role, and permission authority remains entirely in Solomon. Access and
    refresh tokens are intentionally not stored on this record.
    """

    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "issuer",
            "provider_subject",
            name="uq_external_identity_provider_issuer_subject",
        ),
        Index(
            "ix_external_identity_user_provider",
            "user_id",
            "provider",
        ),
        Index(
            "ix_external_identity_normalized_email",
            "normalized_email",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(32), nullable=False, index=True)
    issuer = Column(String(255), nullable=False)
    provider_subject = Column(String(255), nullable=False)
    provider_email = Column(String(255), nullable=True)
    normalized_email = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    tenant_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    last_authenticated_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship(
        "User",
        back_populates="external_identities",
        foreign_keys=[user_id],
    )


class FileRegistry(Base):
    __tablename__ = "file_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    random_name = Column(String(64), unique=True, nullable=False)
    original_name = Column(String(255), nullable=False)
    extension = Column(String(16))
    path = Column(String(512), nullable=False)
    meta = Column(JSON)
    upload_time = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    size_bytes = Column(Integer)
    checksum = Column(String(64))

    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    classification = Column(
        String(32),
        default="internal",
        nullable=False,
        index=True,
    )
    version_number = Column(
        Integer,
        default=1,
        nullable=False,
    )
    version_lineage_id = Column(
        String(64),
        default=new_opaque_id,
        nullable=False,
        index=True,
    )
    version_created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    archived_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    workspace_folder_id = Column(
        String(64),
        ForeignKey(
            "workspace_folders.folder_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    uploader_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    uploader = relationship(
        "User",
        back_populates="files",
        foreign_keys=[uploader_id],
    )
    folder = relationship(
        "WorkspaceFolder",
        back_populates="files",
        foreign_keys=[workspace_folder_id],
    )

    artifact_sources = relationship(
        "WorkspaceArtifactSource",
        back_populates="file",
    )

    solomon_ai_conversation_sources = relationship(
        "SolomonAIConversationSource",
        back_populates="file",
    )

    organization_custodies = relationship(
        "OrganizationFileCustody",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    access_grants = relationship(
        "FileAccessGrant",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    group_access_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    authorization_decisions = relationship(
        "FileAuthorizationDecision",
        back_populates="file",
    )

    workspace_intelligence_objects = relationship(
        "WorkspaceIntelligenceObject",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    solomon_action_result_resources = relationship(
        "SolomonActionResultResource",
        back_populates="file",
        cascade="all, delete-orphan",
    )

    solomon_action_applicability_profile = relationship(
        "SolomonActionApplicabilityProfile",
        back_populates="file",
        cascade="all, delete-orphan",
        uselist=False,
    )

    version_history = relationship(
        "FileVersionHistory",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FileVersionHistory.version_number",
    )

    @property
    def display_name(self) -> str:
        return self.original_name

    @property
    def filename(self) -> str:
        return self.original_name


class FileVersionHistory(Base):
    __tablename__ = "file_version_history"
    __table_args__ = (
        UniqueConstraint(
            "file_registry_id",
            "version_number",
            name="uq_file_version_history_file_version",
        ),
        Index(
            "ix_file_version_history_lineage_version",
            "version_lineage_id",
            "version_number",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_registry_id = Column(
        Integer,
        ForeignKey("file_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_lineage_id = Column(
        String(64),
        nullable=False,
        index=True,
    )
    version_number = Column(Integer, nullable=False)
    original_name = Column(String(255), nullable=False)
    extension = Column(String(16), nullable=True)
    path = Column(String(512), nullable=False)
    size_bytes = Column(Integer, nullable=True)
    checksum = Column(String(64), nullable=True)
    version_created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version_created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    file = relationship(
        "FileRegistry",
        back_populates="version_history",
    )
    version_created_by_user = relationship(
        "User",
        foreign_keys=[version_created_by_user_id],
    )


class FileRecentActivity(Base):
    __tablename__ = "file_recent_activity"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "file_id",
            name="uq_file_recent_activity_user_file",
        ),
        Index(
            "ix_file_recent_activity_user_activity",
            "user_id",
            "activity_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_id = Column(
        Integer,
        ForeignKey("file_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    activity_kind = Column(
        String(32),
        default="opened",
        nullable=False,
    )
    activity_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    user = relationship("User")
    file = relationship("FileRegistry")


class WorkspaceFolder(Base):
    __tablename__ = "workspace_folders"
    __table_args__ = (
        UniqueConstraint(
            "folder_id",
            name="uq_workspace_folder_folder_id",
        ),
        UniqueConstraint(
            "user_id",
            "visibility_scope",
            "parent_folder_key",
            "normalized_name",
            "status",
            name="uq_workspace_folder_owner_parent_name_status",
        ),
        Index(
            "ix_workspace_folder_owner_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_workspace_folder_owner_parent_status",
            "user_id",
            "parent_folder_key",
            "status",
        ),
        Index(
            "ix_workspace_folder_group_status",
            "organization_id",
            "group_id",
            "status",
        ),
        Index(
            "ix_workspace_folder_status_updated",
            "status",
            "updated_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    folder_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    folder_contract = Column(
        String(128),
        default=WORKSPACE_FOLDER_CONTRACT,
        nullable=False,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_folder_id = Column(
        String(64),
        ForeignKey(
            "workspace_folders.folder_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    parent_folder_key = Column(
        String(64),
        default=WORKSPACE_FOLDER_ROOT_PARENT_KEY,
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    group_id = Column(
        String(64),
        ForeignKey(
            "organization_groups.group_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False, index=True)
    path_key = Column(String(512), nullable=False, index=True)
    depth = Column(Integer, default=0, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    visibility_scope = Column(
        String(64),
        default=WORKSPACE_FOLDER_OWNER_SCOPE,
        nullable=False,
        index=True,
    )
    is_discoverable = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    metadata_json = Column(JSON, nullable=True)

    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    owner_user = relationship(
        "User",
        back_populates="workspace_folders",
        foreign_keys=[user_id],
    )
    created_by_user = relationship(
        "User",
        foreign_keys=[created_by_user_id],
    )
    updated_by_user = relationship(
        "User",
        foreign_keys=[updated_by_user_id],
    )
    parent = relationship(
        "WorkspaceFolder",
        remote_side=[folder_id],
        back_populates="children",
        foreign_keys=[parent_folder_id],
    )
    children = relationship(
        "WorkspaceFolder",
        back_populates="parent",
        foreign_keys=[parent_folder_id],
    )
    organization = relationship(
        "Organization",
        back_populates="workspace_folders",
    )
    group = relationship(
        "OrganizationGroup",
        back_populates="workspace_folders",
    )
    files = relationship(
        "FileRegistry",
        back_populates="folder",
        foreign_keys="FileRegistry.workspace_folder_id",
    )
    access_grants = relationship(
        "FolderAccessGrant",
        back_populates="folder",
        cascade="all, delete-orphan",
    )
    group_access_grants = relationship(
        "FolderGroupAccessGrant",
        back_populates="folder",
        cascade="all, delete-orphan",
    )


# ===============================================================
# GROUP ACCOUNT / MEMBERSHIP / DOCUMENT AUTHORITY
# ===============================================================
# NOTE:
# These ORM class and table names remain as a temporary database bridge while
# the active product namespace moves to People and Groups. New code may import
# the canonical aliases near the bottom of this file, while the later MySQL
# migration can rename physical tables and columns deliberately.
class Organization(Base):
    __tablename__ = "organizations"

    organization_id = Column(
        String(64),
        primary_key=True,
        default=new_opaque_id,
    )
    name = Column(String(255), nullable=False)
    slug = Column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )
    legal_name = Column(
        String(255),
        nullable=True,
    )
    verified_domain = Column(
        String(255),
        nullable=True,
        index=True,
    )
    verification_status = Column(
        String(32),
        default="unverified",
        nullable=False,
        index=True,
    )
    verification_updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    authorization_policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    default_file_visibility = Column(
        String(64),
        default=GROUP_LIBRARY_SCOPE,
        nullable=False,
        index=True,
    )
    ai_query_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    suspended_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    created_by = relationship(
        "User",
        back_populates="organizations_created",
        foreign_keys=[created_by_user_id],
    )

    memberships = relationship(
        "OrganizationMembership",
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrganizationMembership.created_at",
    )

    file_custodies = relationship(
        "OrganizationFileCustody",
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrganizationFileCustody.created_at",
    )

    workspace_folders = relationship(
        "WorkspaceFolder",
        back_populates="organization",
    )

    file_access_grants = relationship(
        "FileAccessGrant",
        back_populates="organization",
    )

    groups = relationship(
        "OrganizationGroup",
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrganizationGroup.created_at",
    )

    group_file_access_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="organization",
    )

    authorization_decisions = relationship(
        "FileAuthorizationDecision",
        back_populates="organization",
    )

    conversation_contexts = relationship(
        "SolomonAIConversationOrganizationContext",
        back_populates="organization",
    )

    intelligence_objects = relationship(
        "WorkspaceIntelligenceObject",
        back_populates="organization",
    )

    invitations = relationship(
        "OrganizationInvitation",
        back_populates="organization",
        cascade="all, delete-orphan",
        order_by="OrganizationInvitation.created_at",
    )

    audit_events = relationship(
        "OrganizationAuditEvent",
        back_populates="organization",
        order_by="OrganizationAuditEvent.created_at",
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_membership",
        ),
        Index(
            "ix_organization_membership_user_status",
            "user_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    role = Column(
        String(32),
        default="member",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    is_primary = Column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    invited_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    joined_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="memberships",
    )
    user = relationship(
        "User",
        back_populates="organization_memberships",
        foreign_keys=[user_id],
    )
    invited_by_user = relationship(
        "User",
        foreign_keys=[invited_by_user_id],
    )

    invitations = relationship(
        "OrganizationInvitation",
        back_populates="membership",
        foreign_keys="OrganizationInvitation.membership_id",
    )


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        Index(
            "ix_organization_invitation_org_email_status",
            "organization_id",
            "normalized_email",
            "status",
        ),
        Index(
            "ix_organization_invitation_email_status",
            "normalized_email",
            "status",
        ),
        Index(
            "ix_organization_invitation_token_status",
            "token_hash",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    invitation_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    membership_id = Column(
        Integer,
        ForeignKey(
            "organization_memberships.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    email = Column(String(255), nullable=False)
    normalized_email = Column(
        String(255),
        nullable=False,
        index=True,
    )
    role = Column(
        String(32),
        default="member",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    token_hash = Column(
        String(128),
        unique=True,
        nullable=True,
        index=True,
    )
    invitation_contract = Column(
        String(128),
        default=GROUP_MEMBERSHIP_INVITATION_CONTRACT,
        nullable=False,
    )

    invited_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    accepted_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    revoked_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    accepted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revocation_reason = Column(String(255), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    organization = relationship(
        "Organization",
        back_populates="invitations",
    )
    membership = relationship(
        "OrganizationMembership",
        back_populates="invitations",
        foreign_keys=[membership_id],
    )
    invited_by_user = relationship(
        "User",
        back_populates="issued_organization_invitations",
        foreign_keys=[invited_by_user_id],
    )
    accepted_by_user = relationship(
        "User",
        back_populates="accepted_organization_invitations",
        foreign_keys=[accepted_by_user_id],
    )
    revoked_by_user = relationship(
        "User",
        back_populates="revoked_organization_invitations",
        foreign_keys=[revoked_by_user_id],
    )

    intents = relationship(
        "OrganizationInvitationIntent",
        back_populates="invitation",
        cascade="all, delete-orphan",
        order_by="OrganizationInvitationIntent.created_at",
    )


class OrganizationInvitationIntent(Base):
    """Durable action to complete after an invited identity is admitted."""

    __tablename__ = "organization_invitation_intents"
    __table_args__ = (
        Index(
            "ix_organization_invitation_intent_invitation_status",
            "invitation_id",
            "status",
        ),
        Index(
            "ix_organization_invitation_intent_group_status",
            "group_id",
            "status",
        ),
        Index(
            "ix_organization_invitation_intent_file_status",
            "file_registry_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    intent_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    invitation_id = Column(
        Integer,
        ForeignKey(
            "organization_invitations.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    intent_type = Column(
        String(64),
        nullable=False,
        index=True,
    )
    intent_contract = Column(
        String(128),
        default=ORGANIZATION_INVITATION_INTENT_CONTRACT,
        nullable=False,
    )
    status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )

    group_id = Column(
        String(64),
        ForeignKey(
            "organization_groups.group_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    group_role = Column(
        String(32),
        nullable=True,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    completed_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    invitation = relationship(
        "OrganizationInvitation",
        back_populates="intents",
    )
    group = relationship(
        "OrganizationGroup",
    )
    file = relationship(
        "FileRegistry",
    )


class OrganizationAuditEvent(Base):
    __tablename__ = "organization_audit_events"
    __table_args__ = (
        Index(
            "ix_organization_audit_org_event_created",
            "organization_id",
            "event_type",
            "created_at",
        ),
        Index(
            "ix_organization_audit_actor_event_created",
            "actor_user_id",
            "event_type",
            "created_at",
        ),
        Index(
            "ix_organization_audit_target_event_created",
            "target_user_id",
            "event_type",
            "created_at",
        ),
        Index(
            "ix_organization_audit_request_created",
            "request_id",
            "created_at",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    event_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    event_type = Column(
        String(128),
        nullable=False,
        index=True,
    )
    event_contract = Column(
        String(128),
        default=GROUP_AUDIT_EVENT_CONTRACT,
        nullable=False,
    )
    actor_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    target_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    target_email = Column(
        String(255),
        nullable=True,
        index=True,
    )
    invitation_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    membership_id = Column(
        Integer,
        nullable=True,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    role_before = Column(
        String(32),
        nullable=True,
    )
    role_after = Column(
        String(32),
        nullable=True,
    )
    decision = Column(
        String(32),
        default="recorded",
        nullable=False,
        index=True,
    )
    reason_code = Column(
        String(128),
        nullable=True,
        index=True,
    )
    request_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    source = Column(
        String(128),
        nullable=True,
        index=True,
    )
    details_json = Column(
        JSON,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="audit_events",
    )
    actor_user = relationship(
        "User",
        back_populates="organization_audit_events_as_actor",
        foreign_keys=[actor_user_id],
    )
    target_user = relationship(
        "User",
        back_populates="organization_audit_events_as_target",
        foreign_keys=[target_user_id],
    )
    file = relationship(
        "FileRegistry",
    )


class OrganizationGroup(Base):
    __tablename__ = "organization_groups"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "slug",
            name="uq_organization_group_slug",
        ),
        Index(
            "ix_organization_group_org_status",
            "organization_id",
            "status",
        ),
    )

    group_id = Column(
        String(64),
        primary_key=True,
        default=new_opaque_id,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    name = Column(String(255), nullable=False)
    description = Column(
        String(1024),
        nullable=True,
    )
    slug = Column(
        String(128),
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    created_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="groups",
    )
    created_by = relationship(
        "User",
        back_populates="organization_groups_created",
        foreign_keys=[created_by_user_id],
    )
    memberships = relationship(
        "OrganizationGroupMembership",
        back_populates="group",
        cascade="all, delete-orphan",
        order_by="OrganizationGroupMembership.created_at",
    )
    file_access_grants = relationship(
        "FileGroupAccessGrant",
        back_populates="group",
        cascade="all, delete-orphan",
    )

    workspace_folders = relationship(
        "WorkspaceFolder",
        back_populates="group",
    )

    intelligence_objects = relationship(
        "WorkspaceIntelligenceObject",
        back_populates="group",
    )


class OrganizationGroupMembership(Base):
    __tablename__ = "organization_group_memberships"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "user_id",
            name="uq_organization_group_membership",
        ),
        Index(
            "ix_organization_group_membership_user_status",
            "user_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    group_id = Column(
        String(64),
        ForeignKey(
            "organization_groups.group_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    role = Column(
        String(32),
        default="member",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    added_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    joined_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    group = relationship(
        "OrganizationGroup",
        back_populates="memberships",
    )
    user = relationship(
        "User",
        back_populates="organization_group_memberships",
        foreign_keys=[user_id],
    )
    added_by_user = relationship(
        "User",
        back_populates="organization_group_memberships_added",
        foreign_keys=[added_by_user_id],
    )


class OrganizationFileCustody(Base):
    __tablename__ = "organization_file_custody"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "file_registry_id",
            name="uq_organization_file_custody",
        ),
        Index(
            "ix_organization_file_custody_org_status",
            "organization_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    custody_mode = Column(
        String(64),
        default=GROUP_CONTROLLED_CUSTODY_MODE,
        nullable=False,
        index=True,
    )
    library_scope = Column(
        String(64),
        default=GROUP_LIBRARY_SCOPE,
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    is_discoverable = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_ai_query = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    classification = Column(
        String(32),
        default="internal",
        nullable=False,
        index=True,
    )
    policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    added_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    removed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    organization = relationship(
        "Organization",
        back_populates="file_custodies",
    )
    file = relationship(
        "FileRegistry",
        back_populates="organization_custodies",
    )
    added_by_user = relationship(
        "User",
        foreign_keys=[added_by_user_id],
    )


class FileAccessGrant(Base):
    __tablename__ = "file_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "file_registry_id",
            "granted_to_user_id",
            name="uq_file_access_grant_recipient",
        ),
        Index(
            "ix_file_access_grant_recipient_status",
            "granted_to_user_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    granted_to_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    granted_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    grant_type = Column(
        String(32),
        default="direct_user",
        nullable=False,
        index=True,
    )
    permission = Column(
        String(32),
        default="view",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    is_discoverable = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_ai_query = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_download = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revoked_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    revocation_reason = Column(
        String(255),
        nullable=True,
    )

    file = relationship(
        "FileRegistry",
        back_populates="access_grants",
    )
    organization = relationship(
        "Organization",
        back_populates="file_access_grants",
    )
    granted_to_user = relationship(
        "User",
        back_populates="received_file_grants",
        foreign_keys=[granted_to_user_id],
    )
    granted_by_user = relationship(
        "User",
        back_populates="issued_file_grants",
        foreign_keys=[granted_by_user_id],
    )
    revoked_by_user = relationship(
        "User",
        back_populates="revoked_file_grants",
        foreign_keys=[revoked_by_user_id],
    )


class FileGroupAccessGrant(Base):
    __tablename__ = "file_group_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "file_registry_id",
            "group_id",
            name="uq_file_group_access_grant_recipient",
        ),
        Index(
            "ix_file_group_access_grant_group_status",
            "group_id",
            "status",
        ),
        Index(
            "ix_file_group_access_grant_org_status",
            "organization_id",
            "status",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    group_id = Column(
        String(64),
        ForeignKey(
            "organization_groups.group_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    granted_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    revoked_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    grant_type = Column(
        String(32),
        default=GROUP_FILE_ACCESS_GRANT_TYPE,
        nullable=False,
        index=True,
    )
    permission = Column(
        String(32),
        default="view",
        nullable=False,
        index=True,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    is_discoverable = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_ai_query = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_download = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    revoked_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    revocation_reason = Column(
        String(255),
        nullable=True,
    )

    file = relationship(
        "FileRegistry",
        back_populates="group_access_grants",
    )
    organization = relationship(
        "Organization",
        back_populates="group_file_access_grants",
    )
    group = relationship(
        "OrganizationGroup",
        back_populates="file_access_grants",
    )
    granted_by_user = relationship(
        "User",
        back_populates="issued_group_file_grants",
        foreign_keys=[granted_by_user_id],
    )
    revoked_by_user = relationship(
        "User",
        back_populates="revoked_group_file_grants",
        foreign_keys=[revoked_by_user_id],
    )


class FolderAccessGrant(Base):
    __tablename__ = "folder_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "workspace_folder_id",
            "granted_to_user_id",
            name="uq_folder_access_grant_recipient",
        ),
        Index(
            "ix_folder_access_grant_recipient_status",
            "granted_to_user_id",
            "status",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_folder_id = Column(
        String(64),
        ForeignKey("workspace_folders.folder_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey("organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    granted_to_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    granted_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    revoked_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    grant_type = Column(
        String(32),
        default=FOLDER_ACCESS_GRANT_TYPE,
        nullable=False,
        index=True,
    )
    permission = Column(String(32), default="view", nullable=False, index=True)
    status = Column(String(32), default="active", nullable=False, index=True)
    is_discoverable = Column(Boolean, default=True, nullable=False, index=True)
    allow_ai_query = Column(Boolean, default=True, nullable=False, index=True)
    allow_download = Column(Boolean, default=True, nullable=False, index=True)
    policy_version = Column(
        String(64),
        default=WORKSPACE_FOLDER_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    revocation_reason = Column(String(255), nullable=True)

    folder = relationship("WorkspaceFolder", back_populates="access_grants")
    granted_to_user = relationship("User", foreign_keys=[granted_to_user_id])
    granted_by_user = relationship("User", foreign_keys=[granted_by_user_id])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by_user_id])


class FolderGroupAccessGrant(Base):
    __tablename__ = "folder_group_access_grants"
    __table_args__ = (
        UniqueConstraint(
            "workspace_folder_id",
            "group_id",
            name="uq_folder_group_access_grant_recipient",
        ),
        Index(
            "ix_folder_group_access_grant_group_status",
            "group_id",
            "status",
        ),
        Index(
            "ix_folder_group_access_grant_org_status",
            "organization_id",
            "status",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    workspace_folder_id = Column(
        String(64),
        ForeignKey("workspace_folders.folder_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey("organizations.organization_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    group_id = Column(
        String(64),
        ForeignKey("organization_groups.group_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    granted_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    revoked_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    grant_type = Column(
        String(32),
        default=FOLDER_GROUP_ACCESS_GRANT_TYPE,
        nullable=False,
        index=True,
    )
    permission = Column(String(32), default="view", nullable=False, index=True)
    status = Column(String(32), default="active", nullable=False, index=True)
    is_discoverable = Column(Boolean, default=True, nullable=False, index=True)
    allow_ai_query = Column(Boolean, default=True, nullable=False, index=True)
    allow_download = Column(Boolean, default=True, nullable=False, index=True)
    policy_version = Column(
        String(64),
        default=WORKSPACE_FOLDER_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True, index=True)
    revocation_reason = Column(String(255), nullable=True)

    folder = relationship("WorkspaceFolder", back_populates="group_access_grants")
    organization = relationship("Organization")
    group = relationship("OrganizationGroup")
    granted_by_user = relationship("User", foreign_keys=[granted_by_user_id])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by_user_id])


class FileAuthorizationDecision(Base):
    __tablename__ = "file_authorization_decisions"
    __table_args__ = (
        Index(
            "ix_file_authorization_actor_action_created",
            "actor_user_id",
            "action",
            "created_at",
        ),
        Index(
            "ix_file_authorization_resource_action_created",
            "file_registry_id",
            "action",
            "created_at",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    request_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    case_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    manifest_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    actor_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    action = Column(
        String(32),
        nullable=False,
        index=True,
    )
    decision = Column(
        String(16),
        nullable=False,
        index=True,
    )
    reason_code = Column(
        String(64),
        nullable=False,
        index=True,
    )
    access_scope = Column(
        String(64),
        nullable=True,
        index=True,
    )
    permission = Column(
        String(32),
        nullable=True,
        index=True,
    )
    policy_version = Column(
        String(64),
        default=GROUP_FILE_PERMISSION_POLICY_VERSION,
        nullable=False,
    )
    details_json = Column(
        JSON,
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    actor_user = relationship(
        "User",
        back_populates="file_authorization_decisions",
        foreign_keys=[actor_user_id],
    )
    organization = relationship(
        "Organization",
        back_populates="authorization_decisions",
    )
    file = relationship(
        "FileRegistry",
        back_populates="authorization_decisions",
    )


class BidReviewRecord(Base):
    __tablename__ = "bid_review_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    review_title = Column(String(255), nullable=False)
    review_mode = Column(
        String(32),
        nullable=False,
        index=True,
    )
    document_names = Column(Text, nullable=True)

    risk_level = Column(
        String(64),
        nullable=True,
        index=True,
    )
    scope_completeness = Column(
        String(64),
        nullable=True,
        index=True,
    )
    report_html = Column(Text, nullable=True)
    structured_payload = Column(Text, nullable=True)

    status = Column(
        String(32),
        default="completed",
        nullable=False,
        index=True,
    )
    analysis_version = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    user = relationship(
        "User",
        back_populates="bid_review_records",
    )


# ===============================================================
# WORKSPACE ARTIFACTS / SAVED REVIEWS
# ===============================================================
class WorkspaceArtifact(Base):
    __tablename__ = "workspace_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    artifact_type = Column(
        String(64),
        default="review",
        nullable=False,
        index=True,
    )
    report_type = Column(
        String(128),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=True)

    status = Column(
        String(32),
        default="completed",
        nullable=False,
        index=True,
    )
    risk_level = Column(
        String(64),
        nullable=True,
        index=True,
    )
    scope_completeness = Column(
        String(64),
        nullable=True,
        index=True,
    )
    confidence_level = Column(
        String(64),
        nullable=True,
        index=True,
    )

    operation_key = Column(
        String(128),
        nullable=True,
        index=True,
    )
    job_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    request_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    analysis_version = Column(String(64), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="workspace_artifacts",
    )

    sources = relationship(
        "WorkspaceArtifactSource",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="WorkspaceArtifactSource.source_order",
    )

    sections = relationship(
        "WorkspaceArtifactSection",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="WorkspaceArtifactSection.section_order",
    )

    findings = relationship(
        "WorkspaceArtifactFinding",
        back_populates="artifact",
        cascade="all, delete-orphan",
        order_by="WorkspaceArtifactFinding.sort_order",
    )

    audit_payloads = relationship(
        "WorkspaceArtifactAuditPayload",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )

    review_set_items = relationship(
        "ReviewSetItem",
        back_populates="artifact",
        cascade="all, delete-orphan",
    )


class WorkspaceArtifactSource(Base):
    __tablename__ = "workspace_artifact_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    source_document_id = Column(
        String(128),
        nullable=True,
        index=True,
    )
    source_name = Column(String(255), nullable=False)
    source_type = Column(
        String(64),
        default="document",
        nullable=False,
        index=True,
    )
    source_order = Column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="sources",
    )
    file = relationship(
        "FileRegistry",
        back_populates="artifact_sources",
    )


class WorkspaceArtifactSection(Base):
    __tablename__ = "workspace_artifact_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    section_key = Column(
        String(128),
        nullable=True,
        index=True,
    )
    section_title = Column(String(255), nullable=False)
    section_order = Column(
        Integer,
        default=0,
        nullable=False,
    )
    body_html = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="sections",
    )


class WorkspaceArtifactFinding(Base):
    __tablename__ = "workspace_artifact_findings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    source_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifact_sources.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    finding_type = Column(
        String(128),
        nullable=True,
        index=True,
    )
    severity = Column(
        String(64),
        nullable=True,
        index=True,
    )
    title = Column(String(255), nullable=False)
    finding_text = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)

    source_document_id = Column(
        String(128),
        nullable=True,
        index=True,
    )
    page_number = Column(Integer, nullable=True)
    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="findings",
    )
    source = relationship("WorkspaceArtifactSource")


class ReviewSet(Base):
    __tablename__ = "review_sets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="review_sets",
    )

    items = relationship(
        "ReviewSetItem",
        back_populates="review_set",
        cascade="all, delete-orphan",
        order_by="ReviewSetItem.sort_order",
    )


class ReviewSetItem(Base):
    __tablename__ = "review_set_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    review_set_id = Column(
        Integer,
        ForeignKey(
            "review_sets.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    review_set = relationship(
        "ReviewSet",
        back_populates="items",
    )
    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="review_set_items",
    )


class WorkspaceArtifactAuditPayload(Base):
    __tablename__ = "workspace_artifact_audit_payloads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    artifact_id = Column(
        Integer,
        ForeignKey(
            "workspace_artifacts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    payload_kind = Column(
        String(128),
        nullable=False,
        index=True,
    )
    payload_json = Column(JSON, nullable=True)
    payload_text = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    artifact = relationship(
        "WorkspaceArtifact",
        back_populates="audit_payloads",
    )


# ===============================================================
# SOLOMONAI CONVERSATION PERSISTENCE
# ===============================================================
class SolomonAIConversation(Base):
    __tablename__ = "solomon_ai_conversations"

    conversation_id = Column(
        String(64),
        primary_key=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(
        String(255),
        default="New conversation",
        nullable=False,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    contract = Column(
        String(128),
        default="document_ai_explicit_source_session",
        nullable=False,
    )
    source_membership_contract = Column(
        String(128),
        default="solomon_ai_conversation_source_membership_v1",
        nullable=False,
    )
    operation_key = Column(
        String(128),
        default="ask_solomon_ai",
        nullable=False,
        index=True,
    )
    public_web_selected = Column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )
    last_message_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="solomon_ai_conversations",
    )

    sources = relationship(
        "SolomonAIConversationSource",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SolomonAIConversationSource.source_order",
    )

    messages = relationship(
        "SolomonAIConversationMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="SolomonAIConversationMessage.message_order",
    )

    organization_context = relationship(
        "SolomonAIConversationOrganizationContext",
        back_populates="conversation",
        cascade="all, delete-orphan",
        uselist=False,
    )

    workspace_intelligence_objects = relationship(
        "WorkspaceIntelligenceObject",
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class SolomonAIConversationSource(Base):
    __tablename__ = "solomon_ai_conversation_sources"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "source_document_id",
            name="uq_solomon_ai_conversation_source",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        String(64),
        ForeignKey(
            "solomon_ai_conversations.conversation_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    source_document_id = Column(
        String(128),
        nullable=False,
        index=True,
    )
    source_name = Column(String(255), nullable=False)
    source_order = Column(
        Integer,
        default=0,
        nullable=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    conversation = relationship(
        "SolomonAIConversation",
        back_populates="sources",
    )
    file = relationship(
        "FileRegistry",
        back_populates="solomon_ai_conversation_sources",
    )


class SolomonAIConversationOrganizationContext(Base):
    __tablename__ = "solomon_ai_conversation_organization_context"

    conversation_id = Column(
        String(64),
        ForeignKey(
            "solomon_ai_conversations.conversation_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    membership_id = Column(
        Integer,
        ForeignKey(
            "organization_memberships.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    bound_by_user_id = Column(
        Integer,
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    conversation = relationship(
        "SolomonAIConversation",
        back_populates="organization_context",
    )
    organization = relationship(
        "Organization",
        back_populates="conversation_contexts",
    )
    membership = relationship(
        "OrganizationMembership",
    )
    bound_by_user = relationship(
        "User",
        foreign_keys=[bound_by_user_id],
    )


class SolomonAIConversationMessage(Base):
    __tablename__ = "solomon_ai_conversation_messages"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "message_order",
            name="uq_solomon_ai_conversation_message_order",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        String(64),
        ForeignKey(
            "solomon_ai_conversations.conversation_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    role = Column(
        String(32),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    bridge = Column(Text, nullable=True)
    suggestions = Column(JSON, nullable=True)
    request_id = Column(
        String(64),
        nullable=True,
        index=True,
    )
    message_order = Column(Integer, nullable=False)
    status = Column(
        String(32),
        default="complete",
        nullable=False,
        index=True,
    )
    packet_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    conversation = relationship(
        "SolomonAIConversation",
        back_populates="messages",
    )


# ===============================================================
# WORKSPACE INTELLIGENCE INDEX
# ===============================================================
class WorkspaceIntelligenceObject(Base):
    __tablename__ = "workspace_intelligence_objects"
    __table_args__ = (
        UniqueConstraint(
            "object_type",
            "file_registry_id",
            name="uq_workspace_intelligence_file_object",
        ),
        UniqueConstraint(
            "object_type",
            "conversation_id",
            name="uq_workspace_intelligence_conversation_object",
        ),
        UniqueConstraint(
            "object_type",
            "subject_user_id",
            "organization_id",
            name="uq_workspace_intelligence_person_object",
        ),
        UniqueConstraint(
            "object_type",
            "group_id",
            name="uq_workspace_intelligence_group_object",
        ),
        Index(
            "ix_workspace_intelligence_owner_type_status",
            "user_id",
            "object_type",
            "status",
        ),
        Index(
            "ix_workspace_intelligence_org_type_status",
            "organization_id",
            "object_type",
            "status",
        ),
        Index(
            "ix_workspace_intelligence_group_type_status",
            "group_id",
            "object_type",
            "status",
        ),
        Index(
            "ix_workspace_intelligence_file_status",
            "file_registry_id",
            "status",
        ),
        Index(
            "ix_workspace_intelligence_conversation_status",
            "conversation_id",
            "status",
        ),
        Index(
            "ix_workspace_intelligence_index_status",
            "index_status",
            "updated_at",
        ),
        Index(
            "ix_workspace_intelligence_ai_query_status",
            "allow_ai_query",
            "is_discoverable",
            "status",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    intelligence_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    object_contract = Column(
        String(128),
        default=WORKSPACE_INTELLIGENCE_OBJECT_CONTRACT,
        nullable=False,
    )
    object_type = Column(
        String(32),
        nullable=False,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey(
            "organizations.organization_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    group_id = Column(
        String(64),
        ForeignKey(
            "organization_groups.group_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey(
            "file_registry.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )
    conversation_id = Column(
        String(64),
        ForeignKey(
            "solomon_ai_conversations.conversation_id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )
    subject_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title = Column(String(255), nullable=False)
    subtitle = Column(String(255), nullable=True)
    canonical_url = Column(String(512), nullable=False)
    icon_key = Column(
        String(64),
        default="search",
        nullable=False,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    visibility_scope = Column(
        String(64),
        default="owner",
        nullable=False,
        index=True,
    )
    is_discoverable = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    allow_ai_query = Column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    short_summary = Column(Text, nullable=True)
    detailed_summary = Column(Text, nullable=True)
    search_text = Column(Text, nullable=True)
    keywords_json = Column(JSON, nullable=True)
    structured_facts_json = Column(JSON, nullable=True)
    source_locator_json = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    source_hash = Column(String(128), nullable=True, index=True)
    extracted_text_hash = Column(String(128), nullable=True)
    summary_hash = Column(String(128), nullable=True)
    facts_hash = Column(String(128), nullable=True)

    extraction_status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    summary_status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    facts_status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    embedding_status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    index_status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    stale_reason = Column(String(255), nullable=True)
    error_message = Column(Text, nullable=True)

    embedding_contract = Column(
        String(128),
        default=WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
        nullable=False,
    )
    embedding_model = Column(String(128), nullable=True, index=True)
    embedding_ref = Column(String(512), nullable=True)
    embedding_vector = Column(JSON, nullable=True)
    embedding_dimension = Column(Integer, nullable=True)
    embedding_checksum = Column(String(128), nullable=True)

    indexed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    extracted_at = Column(DateTime(timezone=True), nullable=True)
    summarized_at = Column(DateTime(timezone=True), nullable=True)
    facts_extracted_at = Column(DateTime(timezone=True), nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )
    deleted_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    owner_user = relationship(
        "User",
        back_populates="workspace_intelligence_objects",
        foreign_keys=[user_id],
    )
    subject_user = relationship(
        "User",
        back_populates="workspace_intelligence_subject_objects",
        foreign_keys=[subject_user_id],
    )
    organization = relationship(
        "Organization",
        back_populates="intelligence_objects",
    )
    group = relationship(
        "OrganizationGroup",
        back_populates="intelligence_objects",
    )
    file = relationship(
        "FileRegistry",
        back_populates="workspace_intelligence_objects",
    )
    conversation = relationship(
        "SolomonAIConversation",
        back_populates="workspace_intelligence_objects",
    )
    chunks = relationship(
        "WorkspaceIntelligenceChunk",
        back_populates="intelligence_object",
        cascade="all, delete-orphan",
        order_by="WorkspaceIntelligenceChunk.chunk_order",
    )
    facts = relationship(
        "WorkspaceIntelligenceFact",
        back_populates="intelligence_object",
        cascade="all, delete-orphan",
        order_by="WorkspaceIntelligenceFact.sort_order",
    )


class WorkspaceIntelligenceChunk(Base):
    __tablename__ = "workspace_intelligence_chunks"
    __table_args__ = (
        UniqueConstraint(
            "intelligence_object_id",
            "chunk_order",
            name="uq_workspace_intelligence_chunk_order",
        ),
        Index(
            "ix_workspace_intelligence_chunk_object_kind",
            "intelligence_object_id",
            "chunk_kind",
        ),
        Index(
            "ix_workspace_intelligence_chunk_embedding_status",
            "embedding_status",
            "updated_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    intelligence_object_id = Column(
        Integer,
        ForeignKey(
            "workspace_intelligence_objects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    chunk_contract = Column(
        String(128),
        default=WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT,
        nullable=False,
    )
    chunk_kind = Column(
        String(64),
        default="body",
        nullable=False,
        index=True,
    )
    chunk_order = Column(
        Integer,
        default=0,
        nullable=False,
    )
    title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String(128), nullable=False, index=True)
    token_count = Column(Integer, nullable=True)
    source_locator_json = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    embedding_status = Column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    embedding_contract = Column(
        String(128),
        default=WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
        nullable=False,
    )
    embedding_model = Column(String(128), nullable=True, index=True)
    embedding_ref = Column(String(512), nullable=True)
    embedding_vector = Column(JSON, nullable=True)
    embedding_dimension = Column(Integer, nullable=True)
    embedding_checksum = Column(String(128), nullable=True)
    embedded_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    intelligence_object = relationship(
        "WorkspaceIntelligenceObject",
        back_populates="chunks",
    )


class WorkspaceIntelligenceFact(Base):
    __tablename__ = "workspace_intelligence_facts"
    __table_args__ = (
        Index(
            "ix_workspace_intelligence_fact_object_type",
            "intelligence_object_id",
            "fact_type",
        ),
        Index(
            "ix_workspace_intelligence_fact_key",
            "fact_key",
            "fact_type",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    fact_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    intelligence_object_id = Column(
        Integer,
        ForeignKey(
            "workspace_intelligence_objects.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    fact_contract = Column(
        String(128),
        default=WORKSPACE_INTELLIGENCE_FACT_CONTRACT,
        nullable=False,
    )
    fact_type = Column(
        String(64),
        default="general",
        nullable=False,
        index=True,
    )
    fact_key = Column(
        String(128),
        nullable=False,
        index=True,
    )
    fact_label = Column(String(255), nullable=False)
    fact_value = Column(Text, nullable=True)
    fact_value_json = Column(JSON, nullable=True)
    normalized_value = Column(String(512), nullable=True, index=True)
    source_quote = Column(Text, nullable=True)
    source_locator_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    sort_order = Column(
        Integer,
        default=0,
        nullable=False,
    )
    status = Column(
        String(32),
        default="active",
        nullable=False,
        index=True,
    )
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    intelligence_object = relationship(
        "WorkspaceIntelligenceObject",
        back_populates="facts",
    )


# ===============================================================
# SOLOMON ACTION APPLICABILITY / RESOURCE CAPABILITY CACHE
# ===============================================================
class SolomonActionApplicabilityProfile(Base):
    """Versioned deterministic Action applicability for one governed file.

    This profile is a refreshable capability cache, not an authorization grant.
    Runtime Action resolution must still intersect the current registry, current
    file authority, prerequisites/readiness, rollout policy, and entitlement.
    """

    __tablename__ = "solomon_action_applicability_profiles"
    __table_args__ = (
        UniqueConstraint(
            "file_registry_id",
            name="uq_solomon_action_applicability_file",
        ),
        Index(
            "ix_solomon_action_applicability_registry",
            "registry_fingerprint",
        ),
        Index(
            "ix_solomon_action_applicability_source",
            "source_hash",
            "source_version",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    profile_contract = Column(
        String(128),
        default=SOLOMON_ACTION_APPLICABILITY_PROFILE_CONTRACT,
        nullable=False,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey("file_registry.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_version = Column(Integer, nullable=False, default=1)
    source_hash = Column(String(128), nullable=True)
    resource_type = Column(String(32), default="file", nullable=False, index=True)
    resource_extension = Column(String(32), nullable=True, index=True)
    registry_fingerprint = Column(String(64), nullable=False)
    applicable_action_ids_json = Column(JSON, nullable=False)
    resource_characteristics_json = Column(JSON, nullable=True)
    evaluated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    file = relationship(
        "FileRegistry",
        back_populates="solomon_action_applicability_profile",
        foreign_keys=[file_registry_id],
    )


# ===============================================================
# SOLOMON ACTION RESULTS / DURABLE DERIVED INTELLIGENCE
# ===============================================================
class SolomonActionResult(Base):
    """Canonical reusable result produced by one qualified Solomon Action contract.

    Results are content-bound, not permission-bearing. Authorization is always
    re-resolved against the current governed resource before a result is exposed.
    """

    __tablename__ = "solomon_action_results"
    __table_args__ = (
        UniqueConstraint(
            "action_id",
            "action_contract_version",
            "source_hash",
            "parameters_hash",
            name="uq_solomon_action_result_identity",
        ),
        Index(
            "ix_solomon_action_result_lookup",
            "action_id",
            "source_hash",
            "status",
        ),
        Index(
            "ix_solomon_action_result_type_status",
            "result_type",
            "status",
        ),
        Index(
            "ix_solomon_action_result_completed",
            "completed_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    result_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    result_contract = Column(
        String(128),
        default=SOLOMON_ACTION_RESULT_CONTRACT,
        nullable=False,
    )
    action_id = Column(String(128), nullable=False, index=True)
    action_contract_version = Column(String(64), nullable=False)
    source_type = Column(String(32), default="file", nullable=False, index=True)
    source_hash = Column(String(128), nullable=False, index=True)
    parameters_hash = Column(String(64), nullable=False)
    parameters_json = Column(JSON, nullable=True)

    status = Column(
        String(32),
        default=SOLOMON_ACTION_RESULT_STATUS_READY,
        nullable=False,
        index=True,
    )
    result_type = Column(String(64), nullable=False, index=True)
    result_text = Column(Text, nullable=True)
    result_json = Column(JSON, nullable=True)
    result_hash = Column(String(128), nullable=False, index=True)

    processor_key = Column(String(128), nullable=True, index=True)
    processor_version = Column(String(64), nullable=True)
    model_key = Column(String(128), nullable=True, index=True)
    provenance_json = Column(JSON, nullable=True)
    evidence_json = Column(JSON, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    completed_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    resource_links = relationship(
        "SolomonActionResultResource",
        back_populates="action_result",
        cascade="all, delete-orphan",
    )


class SolomonActionResultResource(Base):
    """Association between reusable Action intelligence and a governed file version."""

    __tablename__ = "solomon_action_result_resources"
    __table_args__ = (
        UniqueConstraint(
            "action_result_id",
            "file_registry_id",
            "source_version",
            name="uq_solomon_action_result_resource_version",
        ),
        Index(
            "ix_solomon_action_result_resource_file",
            "file_registry_id",
            "source_version",
        ),
        Index(
            "ix_solomon_action_result_resource_hash",
            "source_hash",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    association_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    association_contract = Column(
        String(128),
        default=SOLOMON_ACTION_RESULT_RESOURCE_CONTRACT,
        nullable=False,
    )
    action_result_id = Column(
        String(64),
        ForeignKey("solomon_action_results.result_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey("file_registry.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_version = Column(Integer, nullable=False)
    source_hash = Column(String(128), nullable=False, index=True)
    linked_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    trigger_type = Column(String(64), nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    action_result = relationship(
        "SolomonActionResult",
        back_populates="resource_links",
        foreign_keys=[action_result_id],
    )
    file = relationship(
        "FileRegistry",
        back_populates="solomon_action_result_resources",
        foreign_keys=[file_registry_id],
    )
    linked_by_user = relationship(
        "User",
        foreign_keys=[linked_by_user_id],
    )


# ===============================================================
# SOLOMON INTELLIGENCE SERVICE / DURABLE WORK SPOOL
# ===============================================================
class IntelligenceJob(Base):
    """Durable, leaseable unit of non-authoritative intelligence work.

    The master database is the canonical spool.  SIS workers may disappear or
    retry without losing the requested work.  ``case_id`` is correlation only:
    automatic jobs do not manufacture Investigator CaseFiles.
    """

    __tablename__ = "intelligence_jobs"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_intelligence_job_idempotency_key",
        ),
        Index(
            "ix_intelligence_job_dispatch",
            "status",
            "available_at",
            "priority",
            "created_at",
        ),
        Index(
            "ix_intelligence_job_lease_recovery",
            "status",
            "lease_expires_at",
        ),
        Index(
            "ix_intelligence_job_target",
            "target_type",
            "target_id",
            "target_version",
            "job_type",
        ),
        Index(
            "ix_intelligence_job_file_status",
            "file_registry_id",
            "job_type",
            "status",
        ),
        Index(
            "ix_intelligence_job_case_created",
            "case_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    job_contract = Column(
        String(128),
        default=INTELLIGENCE_JOB_CONTRACT,
        nullable=False,
    )
    job_type = Column(String(128), nullable=False, index=True)
    artifact_type = Column(String(128), nullable=True, index=True)
    request_class = Column(
        String(32),
        default=INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND,
        nullable=False,
        index=True,
    )
    priority = Column(Integer, default=100, nullable=False, index=True)
    status = Column(
        String(32),
        default=INTELLIGENCE_JOB_STATUS_PENDING,
        nullable=False,
        index=True,
    )

    # Idempotency is computed by the enqueue authority from the governed target,
    # source/version identity, requested artifact, and processor contract.
    idempotency_key = Column(String(191), nullable=False)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id = Column(
        String(64),
        ForeignKey("organizations.organization_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_registry_id = Column(
        Integer,
        ForeignKey("file_registry.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    intelligence_object_id = Column(
        Integer,
        ForeignKey("workspace_intelligence_objects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Generic target identity keeps the spool reusable beyond files.  For file
    # jobs target_id is the durable opaque document id and target_version is the
    # FileRegistry version observed when the job was enqueued.
    target_type = Column(String(32), nullable=False, index=True)
    target_id = Column(String(128), nullable=False, index=True)
    target_version = Column(Integer, nullable=True)
    source_hash = Column(String(128), nullable=True, index=True)

    trigger_type = Column(String(64), nullable=False, index=True)
    trigger_ref = Column(String(128), nullable=True, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    case_id = Column(String(64), nullable=True, index=True)

    payload_json = Column(JSON, nullable=True)
    result_json = Column(JSON, nullable=True)
    processor_key = Column(String(128), nullable=True, index=True)
    processor_version = Column(String(64), nullable=True)
    model_key = Column(String(128), nullable=True, index=True)

    attempt_count = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    available_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    worker_id = Column(String(128), nullable=True, index=True)
    lease_token = Column(String(64), nullable=True, index=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True, index=True)

    failure_code = Column(String(128), nullable=True, index=True)
    failure_message = Column(Text, nullable=True)
    last_error_at = Column(DateTime(timezone=True), nullable=True)
    cancel_reason = Column(Text, nullable=True)
    superseded_by_job_id = Column(String(64), nullable=True, index=True)

    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )

    user = relationship("User", foreign_keys=[user_id])
    organization = relationship("Organization", foreign_keys=[organization_id])
    file = relationship("FileRegistry", foreign_keys=[file_registry_id])
    intelligence_object = relationship(
        "WorkspaceIntelligenceObject",
        foreign_keys=[intelligence_object_id],
    )
    events = relationship(
        "IntelligenceJobEvent",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="IntelligenceJobEvent.id",
    )


class IntelligenceJobEvent(Base):
    """Append-oriented operational evidence for an IntelligenceJob."""

    __tablename__ = "intelligence_job_events"
    __table_args__ = (
        Index(
            "ix_intelligence_job_event_job_created",
            "job_id",
            "created_at",
        ),
        Index(
            "ix_intelligence_job_event_type_created",
            "event_type",
            "created_at",
        ),
        Index(
            "ix_intelligence_job_event_worker_created",
            "worker_id",
            "created_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    event_contract = Column(
        String(128),
        default=INTELLIGENCE_JOB_EVENT_CONTRACT,
        nullable=False,
    )
    job_id = Column(
        String(64),
        ForeignKey("intelligence_jobs.job_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(64), nullable=False, index=True)
    stage = Column(String(128), nullable=True, index=True)
    from_status = Column(String(32), nullable=True)
    to_status = Column(String(32), nullable=True, index=True)
    attempt_number = Column(Integer, nullable=True)
    worker_id = Column(String(128), nullable=True, index=True)
    lease_token = Column(String(64), nullable=True)
    request_id = Column(String(64), nullable=True, index=True)
    case_id = Column(String(64), nullable=True, index=True)
    message = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    job = relationship(
        "IntelligenceJob",
        back_populates="events",
        foreign_keys=[job_id],
    )


class IntelligenceComputeEvent(Base):
    """Durable content-free evidence for one governed compute execution.

    Portable SIS measures execution. Solomon persists the authoritative
    historical record without storing prompts, answers, document contents,
    file names, user identity, Group names, or authorization state here.
    Business-scoped reporting may correlate request_id against Solomon-owned
    durable state under normal server-side authorization.
    """

    __tablename__ = "intelligence_compute_events"
    __table_args__ = (
        Index(
            "ix_intelligence_compute_event_node_observed",
            "node_name",
            "observed_at",
        ),
        Index(
            "ix_intelligence_compute_event_priority_observed",
            "priority",
            "observed_at",
        ),
        Index(
            "ix_intelligence_compute_event_workload_observed",
            "workload_type",
            "observed_at",
        ),
        Index(
            "ix_intelligence_compute_event_request_observed",
            "request_id",
            "observed_at",
        ),
        Index(
            "ix_intelligence_compute_event_success_observed",
            "success",
            "observed_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    event_key = Column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    event_contract = Column(
        String(128),
        default=INTELLIGENCE_COMPUTE_EVENT_CONTRACT,
        nullable=False,
    )
    observed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    received_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    node_name = Column(String(128), nullable=False, index=True)
    workload_type = Column(String(64), nullable=False, index=True)
    priority = Column(String(8), nullable=False, index=True)
    request_id = Column(String(128), nullable=True, index=True)
    fairness_bucket = Column(String(128), nullable=False, index=True)
    call_site = Column(String(128), nullable=True, index=True)
    transport_path = Column(String(64), nullable=False, index=True)
    queue_wait_ms = Column(Float, nullable=False, default=0.0)
    execution_ms = Column(Float, nullable=False, default=0.0)
    queue_depth_at_admission = Column(Integer, nullable=False, default=0)
    active_requests_at_admission = Column(Integer, nullable=False, default=0)
    max_concurrent_requests = Column(Integer, nullable=False, default=1)
    input_units = Column(Integer, nullable=True)
    output_units = Column(Integer, nullable=True)
    success = Column(Boolean, nullable=False, default=False, index=True)


class IntelligenceComputeRequestEvent(Base):
    """Durable LOCAL evidence for one outbound compute request attempt.

    This record complements Portable SIS execution telemetry with transport and
    diagnostic facts observed by Solomon. It contains no prompts, answers,
    evidence, file names, user identity, Group names, or permission state.
    """

    __tablename__ = "intelligence_compute_request_events"
    __table_args__ = (
        Index(
            "ix_intelligence_compute_request_event_request_observed",
            "request_id",
            "observed_at",
        ),
        Index(
            "ix_intelligence_compute_request_event_attempt",
            "attempt_id",
        ),
        Index(
            "ix_intelligence_compute_request_event_outcome_observed",
            "outcome_class",
            "observed_at",
        ),
        Index(
            "ix_intelligence_compute_request_event_failure_observed",
            "failure_code",
            "observed_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    request_event_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    event_contract = Column(
        String(128),
        default=INTELLIGENCE_COMPUTE_REQUEST_EVENT_CONTRACT,
        nullable=False,
    )
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    attempt_id = Column(String(64), unique=True, nullable=False, index=True)
    request_id = Column(String(128), nullable=True, index=True)
    compute_event_key = Column(String(64), nullable=True, index=True)
    node_name = Column(String(128), nullable=True, index=True)
    workload_type = Column(String(64), nullable=False, index=True)
    priority = Column(String(8), nullable=False, index=True)
    call_site = Column(String(128), nullable=True, index=True)
    transport_path = Column(String(64), nullable=False, index=True)

    request_bytes = Column(Integer, nullable=False, default=0)
    response_bytes = Column(Integer, nullable=False, default=0)
    round_trip_ms = Column(Float, nullable=False, default=0.0)
    http_status = Column(Integer, nullable=True, index=True)

    remote_execution_observed = Column(Boolean, nullable=False, default=False)
    remote_success = Column(Boolean, nullable=True, index=True)
    outcome_class = Column(String(32), nullable=False, index=True)
    failure_code = Column(String(64), nullable=True, index=True)

    model_name = Column(String(128), nullable=True, index=True)
    runtime_profile = Column(String(64), nullable=True, index=True)
    runtime_fingerprint = Column(String(64), nullable=True, index=True)


class IntelligenceRequestAttribution(Base):
    """Authoritative LOCAL business attribution for one governed request.

    Compute and transport events remain content-free and correlate to this
    record only through request_id. Business identity never crosses to SIS.
    Group attribution is nullable by design and may be populated only when a
    request has an explicit, authoritative Group execution scope.
    """

    __tablename__ = "intelligence_request_attributions"
    __table_args__ = (
        Index(
            "ix_intelligence_request_attribution_user_observed",
            "user_id",
            "observed_at",
        ),
        Index(
            "ix_intelligence_request_attribution_org_observed",
            "organization_id",
            "observed_at",
        ),
        Index(
            "ix_intelligence_request_attribution_group_observed",
            "group_id",
            "observed_at",
        ),
        Index(
            "ix_intelligence_request_attribution_scope_observed",
            "scope_type",
            "observed_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    attribution_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    attribution_contract = Column(
        String(128),
        default=INTELLIGENCE_REQUEST_ATTRIBUTION_CONTRACT,
        nullable=False,
    )
    request_id = Column(String(128), unique=True, nullable=False, index=True)
    observed_at = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    user_id = Column(Integer, nullable=False, index=True)
    organization_id = Column(String(64), nullable=True, index=True)
    group_id = Column(String(64), nullable=True, index=True)
    conversation_id = Column(String(64), nullable=True, index=True)
    case_id = Column(String(64), nullable=True, index=True)

    request_surface = Column(String(64), nullable=False, index=True)
    scope_type = Column(String(32), nullable=False, index=True)
    attribution_source = Column(String(64), nullable=False, index=True)


# ===============================================================
# SOLOMON INTELLIGENCE CAPACITY HISTORY
# ===============================================================
class IntelligenceCapacitySnapshot(Base):
    """Durable LOCAL observation of bounded SIS and spool capacity state.

    Snapshots are recorded from the existing Flask-owned health lifecycle.
    They contain infrastructure state only; prompts, answers, evidence, file
    names, user identity, Group names, and permission state are excluded.
    """

    __tablename__ = "intelligence_capacity_snapshots"
    __table_args__ = (
        Index(
            "ix_intelligence_capacity_snapshot_node_observed",
            "node_name",
            "observed_at",
        ),
        Index(
            "ix_intelligence_capacity_snapshot_status_observed",
            "service_status",
            "observed_at",
        ),
        Index(
            "ix_intelligence_capacity_snapshot_backlog_observed",
            "spool_backlog",
            "observed_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    snapshot_contract = Column(
        String(128),
        default=INTELLIGENCE_CAPACITY_SNAPSHOT_CONTRACT,
        nullable=False,
    )
    observed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    received_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    node_name = Column(String(128), nullable=False, index=True)
    service_status = Column(String(32), nullable=False, index=True)
    service_reachable = Column(Boolean, nullable=False, default=False)
    interactive_ready = Column(Boolean, nullable=False, default=False)
    embedding_ready = Column(Boolean, nullable=False, default=False)
    circuit_open = Column(Boolean, nullable=False, default=False, index=True)
    health_source = Column(String(64), nullable=True, index=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)

    max_concurrent_requests = Column(Integer, nullable=False, default=1)
    active_requests = Column(Integer, nullable=False, default=0)
    waiting_requests = Column(Integer, nullable=False, default=0)
    foreground_waiting = Column(Integer, nullable=False, default=0)
    background_waiting = Column(Integer, nullable=False, default=0)
    oldest_wait_ms = Column(Float, nullable=False, default=0.0)

    p0_active_requests = Column(Integer, nullable=False, default=0)
    p1_active_requests = Column(Integer, nullable=False, default=0)
    p2_active_requests = Column(Integer, nullable=False, default=0)
    p3_active_requests = Column(Integer, nullable=False, default=0)
    p0_waiting_requests = Column(Integer, nullable=False, default=0)
    p1_waiting_requests = Column(Integer, nullable=False, default=0)
    p2_waiting_requests = Column(Integer, nullable=False, default=0)
    p3_waiting_requests = Column(Integer, nullable=False, default=0)

    spool_pending = Column(Integer, nullable=False, default=0)
    spool_retry_wait = Column(Integer, nullable=False, default=0)
    spool_claimed = Column(Integer, nullable=False, default=0)
    spool_running = Column(Integer, nullable=False, default=0)
    spool_backlog = Column(Integer, nullable=False, default=0, index=True)
    spool_in_flight = Column(Integer, nullable=False, default=0)
    spool_unfinished = Column(Integer, nullable=False, default=0)
    oldest_backlog_created_at = Column(DateTime(timezone=True), nullable=True)

    runtime_fingerprint = Column(String(64), nullable=True, index=True)
    runtime_json = Column(JSON, nullable=True)
    embedding_json = Column(JSON, nullable=True)


class IntelligenceCapacityRollup(Base):
    """Derived hourly/daily capacity history owned by LOCAL Solomon.

    Raw compute events, capacity snapshots, and service events remain the
    authoritative evidence. Rollups are reproducible summaries for reporting
    and capacity analysis; they never become execution or authorization truth.
    """

    __tablename__ = "intelligence_capacity_rollups"
    __table_args__ = (
        UniqueConstraint(
            "node_name",
            "period_grain",
            "period_start",
            name="uq_intelligence_capacity_rollup_node_period",
        ),
        Index(
            "ix_intelligence_capacity_rollup_node_period",
            "node_name",
            "period_start",
        ),
        Index(
            "ix_intelligence_capacity_rollup_grain_period",
            "period_grain",
            "period_start",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    rollup_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    rollup_contract = Column(
        String(128),
        default=INTELLIGENCE_CAPACITY_ROLLUP_CONTRACT,
        nullable=False,
    )
    node_name = Column(String(128), nullable=False, index=True)
    period_grain = Column(String(16), nullable=False, index=True)
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    observed_from_at = Column(DateTime(timezone=True), nullable=True)
    observed_through_at = Column(DateTime(timezone=True), nullable=True)
    observation_window_ms = Column(Float, nullable=False, default=0.0)
    refreshed_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
        index=True,
    )

    compute_event_count = Column(Integer, nullable=False, default=0)
    successful_event_count = Column(Integer, nullable=False, default=0)
    failed_event_count = Column(Integer, nullable=False, default=0)
    p0_event_count = Column(Integer, nullable=False, default=0)
    p1_event_count = Column(Integer, nullable=False, default=0)
    p2_event_count = Column(Integer, nullable=False, default=0)
    p3_event_count = Column(Integer, nullable=False, default=0)
    workload_counts_json = Column(JSON, nullable=True)
    transport_counts_json = Column(JSON, nullable=True)

    queue_wait_total_ms = Column(Float, nullable=False, default=0.0)
    queue_wait_avg_ms = Column(Float, nullable=False, default=0.0)
    queue_wait_max_ms = Column(Float, nullable=False, default=0.0)
    queue_depth_at_admission_avg = Column(Float, nullable=False, default=0.0)
    queue_depth_at_admission_peak = Column(Integer, nullable=False, default=0)
    active_requests_at_admission_avg = Column(Float, nullable=False, default=0.0)
    active_requests_at_admission_peak = Column(Integer, nullable=False, default=0)
    execution_total_ms = Column(Float, nullable=False, default=0.0)
    execution_avg_ms = Column(Float, nullable=False, default=0.0)
    execution_max_ms = Column(Float, nullable=False, default=0.0)
    p0_queue_wait_total_ms = Column(Float, nullable=False, default=0.0)
    p0_queue_wait_avg_ms = Column(Float, nullable=False, default=0.0)
    p0_queue_wait_max_ms = Column(Float, nullable=False, default=0.0)
    p0_execution_total_ms = Column(Float, nullable=False, default=0.0)
    p0_execution_avg_ms = Column(Float, nullable=False, default=0.0)
    p0_execution_max_ms = Column(Float, nullable=False, default=0.0)
    p1_queue_wait_total_ms = Column(Float, nullable=False, default=0.0)
    p1_queue_wait_avg_ms = Column(Float, nullable=False, default=0.0)
    p1_queue_wait_max_ms = Column(Float, nullable=False, default=0.0)
    p1_execution_total_ms = Column(Float, nullable=False, default=0.0)
    p1_execution_avg_ms = Column(Float, nullable=False, default=0.0)
    p1_execution_max_ms = Column(Float, nullable=False, default=0.0)

    occupied_execution_ms = Column(Float, nullable=False, default=0.0)
    qualified_capacity_slots = Column(Integer, nullable=False, default=1)
    qualified_capacity_ms = Column(Float, nullable=False, default=0.0)
    qualified_compute_occupancy_pct = Column(Float, nullable=False, default=0.0)
    input_units_total = Column(Integer, nullable=False, default=0)
    output_units_total = Column(Integer, nullable=False, default=0)

    snapshot_count = Column(Integer, nullable=False, default=0)
    reachable_snapshot_count = Column(Integer, nullable=False, default=0)
    ready_snapshot_count = Column(Integer, nullable=False, default=0)
    circuit_open_snapshot_count = Column(Integer, nullable=False, default=0)
    active_requests_avg = Column(Float, nullable=False, default=0.0)
    active_requests_peak = Column(Integer, nullable=False, default=0)
    waiting_requests_avg = Column(Float, nullable=False, default=0.0)
    waiting_requests_peak = Column(Integer, nullable=False, default=0)
    oldest_wait_max_ms = Column(Float, nullable=False, default=0.0)
    spool_backlog_avg = Column(Float, nullable=False, default=0.0)
    spool_backlog_peak = Column(Integer, nullable=False, default=0)
    spool_in_flight_avg = Column(Float, nullable=False, default=0.0)
    spool_in_flight_peak = Column(Integer, nullable=False, default=0)
    oldest_backlog_age_max_seconds = Column(Float, nullable=False, default=0.0)
    max_consecutive_failures = Column(Integer, nullable=False, default=0)

    service_event_count = Column(Integer, nullable=False, default=0)
    availability_transition_count = Column(Integer, nullable=False, default=0)
    unavailable_transition_count = Column(Integer, nullable=False, default=0)
    recovery_transition_count = Column(Integer, nullable=False, default=0)


class IntelligenceServiceEvent(Base):
    """Append-oriented LOCAL evidence for SIS availability transitions."""

    __tablename__ = "intelligence_service_events"
    __table_args__ = (
        Index(
            "ix_intelligence_service_event_node_observed",
            "node_name",
            "observed_at",
        ),
        Index(
            "ix_intelligence_service_event_type_observed",
            "event_type",
            "observed_at",
        ),
        Index(
            "ix_intelligence_service_event_status_observed",
            "to_status",
            "observed_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(
        String(64),
        default=new_opaque_id,
        unique=True,
        nullable=False,
        index=True,
    )
    event_contract = Column(
        String(128),
        default=INTELLIGENCE_SERVICE_EVENT_CONTRACT,
        nullable=False,
    )
    observed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    node_name = Column(String(128), nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    from_status = Column(String(32), nullable=True, index=True)
    to_status = Column(String(32), nullable=False, index=True)
    from_circuit_open = Column(Boolean, nullable=False, default=False)
    to_circuit_open = Column(Boolean, nullable=False, default=False)
    service_reachable = Column(Boolean, nullable=False, default=False)
    health_source = Column(String(64), nullable=True, index=True)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    details_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )


# ===============================================================
# INVESTIGATOR CASEFILES / GOVERNANCE
# ===============================================================
class InvestigatorCaseFile(Base):
    __tablename__ = "investigator_case_files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), unique=True, nullable=False, index=True)
    source = Column(String(128), nullable=False, index=True)
    route = Column(String(128), nullable=True, index=True)
    packet_type = Column(String(128), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    organization_id = Column(String(64), nullable=True, index=True)
    conversation_id = Column(String(64), nullable=True, index=True)
    document_ids_json = Column(JSON, nullable=True)
    prompt_hash = Column(String(64), nullable=True)
    decision_json = Column(JSON, nullable=True)
    evidence_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )


# ===============================================================
# AUTONOMY / GOVERNANCE / LEARNING LOGS
# ===============================================================
class AutonomyLog(Base):
    __tablename__ = "autonomy_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(64), index=True)
    agent_id = Column(String(128), index=True)
    task_type = Column(String(128), index=True)
    description = Column(Text)
    status = Column(String(64), index=True)
    score = Column(Float)
    notes = Column(Text)
    started_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class AutonomyStats(Base):
    __tablename__ = "autonomy_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(10), unique=True, index=True)
    tasks_completed = Column(Integer)
    tasks_failed = Column(Integer)
    avg_score = Column(Float)
    best_task = Column(Text)
    weakest_area = Column(Text)
    recommendations = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class AutonomyState(Base):
    __tablename__ = "autonomy_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state_id = Column(String(64), unique=True, index=True)
    agent_id = Column(String(128), index=True)
    run_id = Column(String(64), index=True)
    task_type = Column(String(128), index=True)
    capability_mode = Column(String(64))
    current_prompt = Column(Text)
    context_json = Column(JSON)
    notes_json = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class SkillRegistry(Base):
    __tablename__ = "skill_registry"

    id = Column(Integer, primary_key=True, autoincrement=True)
    skill_key = Column(String(128), unique=True, nullable=False, index=True)
    skill_name = Column(String(255), nullable=False)
    skill_category = Column(String(128), nullable=False, index=True)
    description = Column(Text)
    owner_agent = Column(String(128), index=True)
    version = Column(String(64), default="1.0.0")
    status = Column(String(64), default="active", index=True)
    review_cadence = Column(String(64))
    last_reviewed_at = Column(DateTime(timezone=True))
    next_review_due_at = Column(DateTime(timezone=True))
    performance_score = Column(Float)
    usage_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    governance_notes = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class SkillUpgradeLog(Base):
    __tablename__ = "skill_upgrade_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    upgrade_id = Column(String(64), unique=True, index=True)
    skill_key = Column(String(128), nullable=False, index=True)
    from_version = Column(String(64))
    to_version = Column(String(64))
    status = Column(String(64), default="proposed", index=True)
    trigger = Column(String(128))
    rationale = Column(Text)
    diff_summary = Column(Text)
    test_results = Column(JSON)
    reviewer = Column(String(128))
    approved_at = Column(DateTime(timezone=True))
    rejected_at = Column(DateTime(timezone=True))
    rollback_id = Column(String(64))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    feedback_id = Column(String(64), unique=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id = Column(String(128))
    feature = Column(String(128), index=True)
    message = Column(Text)
    rating = Column(Integer)
    category = Column(String(128))
    raw_json = Column(JSON)
    status = Column(String(64), default="new", index=True)
    handled_by = Column(String(128))
    handled_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class Correction(Base):
    __tablename__ = "corrections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    correction_id = Column(String(64), unique=True, index=True)
    source_feature = Column(String(128), index=True)
    issue_type = Column(String(128))
    user_feedback_id = Column(String(64), index=True)
    bad_output_hash = Column(String(64))
    corrected_payload = Column(JSON)
    correction_summary = Column(Text)
    status = Column(String(64), default="pending", index=True)
    approved_by = Column(String(128))
    approved_at = Column(DateTime(timezone=True))
    applied_in_version = Column(String(64))
    notes = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class HfloPendingUpgrade(Base):
    __tablename__ = "hflo_pending_upgrades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    package_name = Column(String(255), nullable=False, index=True)
    current_version = Column(String(64))
    latest_version = Column(String(64))
    status = Column(String(64), default="pending", index=True)
    reason = Column(Text)
    source = Column(String(255))
    release_url = Column(Text)
    metadata_json = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class PlannerPatchLog(Base):
    __tablename__ = "planner_patch_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patch_id = Column(String(64), unique=True, index=True)
    source = Column(String(128), index=True)
    target_file = Column(String(512), index=True)
    summary = Column(Text)
    patch_content = Column(Text)
    patch_type = Column(String(64))
    risk_level = Column(String(64))
    status = Column(String(64), default="proposed", index=True)
    approved_by = Column(String(128))
    applied_at = Column(DateTime(timezone=True))
    rejected_at = Column(DateTime(timezone=True))
    rollback_id = Column(String(64))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class PlannerRollbackLog(Base):
    __tablename__ = "planner_rollback_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rollback_id = Column(String(64), unique=True, index=True)
    patch_id = Column(String(64), index=True)
    target_file = Column(String(512), index=True)
    reason = Column(Text)
    restored_content = Column(Text)
    status = Column(String(64), default="pending", index=True)
    performed_by = Column(String(128))
    performed_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class PlanLog(Base):
    __tablename__ = "plan_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(String(64), unique=True, index=True)
    title = Column(String(255), nullable=False)
    goal = Column(Text)
    risk_level = Column(String(64))
    status = Column(String(64), default="planned", index=True)
    owner = Column(String(128))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class PlanStepLog(Base):
    __tablename__ = "plan_step_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    step_id = Column(String(64), unique=True, index=True)
    plan_id = Column(String(64), index=True)
    step_order = Column(Integer)
    title = Column(String(255))
    status = Column(String(64), default="pending", index=True)
    owner = Column(String(128))
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    notes = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class TaskHistory(Base):
    __tablename__ = "task_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, index=True)
    run_id = Column(String(64), index=True)
    agent_id = Column(String(128), index=True)
    parent_task_id = Column(String(64), index=True)
    title = Column(String(255))
    description = Column(Text)
    task_type = Column(String(128))
    status = Column(String(64), default="pending", index=True)
    priority = Column(String(64))
    input_payload = Column(JSON)
    output_payload = Column(JSON)
    failure_reason = Column(Text)
    started_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    finished_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    execution_id = Column(String(64), unique=True, index=True)
    task_id = Column(String(64), index=True)
    run_id = Column(String(64), index=True)
    agent_id = Column(String(128), index=True)
    tool_name = Column(String(128))
    target = Column(String(512))
    status = Column(String(64), default="pending")
    error_message = Column(Text)
    result_snippet = Column(Text)
    started_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )
    finished_at = Column(DateTime(timezone=True))
    metadata_json = Column(JSON)
    reasoning_type = Column(String(255))
    reasoning_source = Column(String(255))


class SecurityLog(Base):
    __tablename__ = "security_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(128))
    username = Column(String(128))
    ip_address = Column(String(64))
    user_agent = Column(Text)
    details_json = Column(JSON)
    created_at = Column(
        DateTime(timezone=True),
        default=utc_now,
    )


# ===============================================================
# CANONICAL PEOPLE / GROUPS MODEL ALIASES
# ===============================================================
# These aliases let new application code speak in the People/Groups namespace
# without forcing an unsafe in-place ORM/table rename before the coordinated
# MySQL migration runs. The legacy ORM names remain exported during the bridge.
Group = Organization
GroupMembership = OrganizationMembership
GroupInvitation = OrganizationInvitation
GroupAuditEvent = OrganizationAuditEvent
GroupFileCustody = OrganizationFileCustody
GroupConversationContext = SolomonAIConversationOrganizationContext


__all__ = [
    "User",
    "FileRegistry",
    "FileRecentActivity",
    "WorkspaceFolder",
    "Group",
    "GroupMembership",
    "GroupInvitation",
    "GroupAuditEvent",
    "GroupFileCustody",
    "GroupConversationContext",
    "Organization",
    "OrganizationMembership",
    "OrganizationInvitation",
    "OrganizationInvitationIntent",
    "OrganizationAuditEvent",
    "OrganizationGroup",
    "OrganizationGroupMembership",
    "OrganizationFileCustody",
    "FileAccessGrant",
    "FileGroupAccessGrant",
    "FolderAccessGrant",
    "FolderGroupAccessGrant",
    "FileAuthorizationDecision",
    "BidReviewRecord",
    "WorkspaceArtifact",
    "WorkspaceArtifactSource",
    "WorkspaceArtifactSection",
    "WorkspaceArtifactFinding",
    "ReviewSet",
    "ReviewSetItem",
    "WorkspaceArtifactAuditPayload",
    "SolomonAIConversation",
    "SolomonAIConversationSource",
    "SolomonAIConversationOrganizationContext",
    "SolomonAIConversationMessage",
    "WorkspaceIntelligenceObject",
    "WorkspaceIntelligenceChunk",
    "WorkspaceIntelligenceFact",
    "IntelligenceJob",
    "IntelligenceJobEvent",
    "IntelligenceComputeEvent",
    "InvestigatorCaseFile",
    "AutonomyLog",
    "AutonomyStats",
    "AutonomyState",
    "SkillRegistry",
    "SkillUpgradeLog",
    "Feedback",
    "Correction",
    "HfloPendingUpgrade",
    "PlannerPatchLog",
    "PlannerRollbackLog",
    "PlanLog",
    "PlanStepLog",
    "TaskHistory",
    "ExecutionLog",
    "SecurityLog",
]
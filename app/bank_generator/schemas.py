from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class CanonicalSectionType(str, Enum):
    summary = "summary"
    experience = "experience"
    projects = "projects"
    skills = "skills"
    education = "education"
    certifications = "certifications"
    publications = "publications"
    achievements = "achievements"
    open_source = "open_source"
    other = "other"


class ResumeSection(BaseModel):
    section_id: str
    heading: str
    raw_text: str
    span_start: int
    span_end: int


class CanonicalSection(BaseModel):
    section_id: str
    canonical_type: CanonicalSectionType
    heading: str


class AtomicEvidenceClaim(BaseModel):
    evidence_id: str
    claim_text: str
    source_section: str
    source_text: str
    source_span_start: int | None = None
    source_span_end: int | None = None
    tools: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    notes: str = ""


class WorkExperienceEntry(BaseModel):
    entry_id: str
    company: str = "Unclear from resume"
    title: str = "Unclear from resume"
    date_range: str = "Unclear from resume"
    location: str = "Unclear from resume"
    evidence_ids: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    project_id: str
    name: str = "Unclear from resume"
    description: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class CapabilityEntry(BaseModel):
    capability_id: str
    name: str
    evidence_ids: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


class DeploymentWorkflow(BaseModel):
    workflow_id: str
    name: str = "Unclear from resume"
    evidence_ids: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)


class MetricEntry(BaseModel):
    metric_id: str
    metric_text: str
    evidence_id: str


class ReusableResumeBullet(BaseModel):
    bullet_id: str
    bullet_text: str
    evidence_ids: list[str] = Field(default_factory=list)
    jd_keywords_supported: list[str] = Field(default_factory=list)


class RetrievalMetadata(BaseModel):
    bank_folder_name: str
    source_file: str
    canonical_type: str
    tools: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    company: str | None = None
    project: str | None = None
    capability: str | None = None
    metrics_available: bool = False


class ExperienceBankIndex(BaseModel):
    bank_folder_name: str
    source_format: Literal["latex", "text"] = "latex"
    sections: list[CanonicalSection] = Field(default_factory=list)
    evidence_claims: list[AtomicEvidenceClaim] = Field(default_factory=list)
    work_experience: list[WorkExperienceEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    capabilities: list[CapabilityEntry] = Field(default_factory=list)
    deployments: list[DeploymentWorkflow] = Field(default_factory=list)
    metrics: list[MetricEntry] = Field(default_factory=list)
    reusable_bullets: list[ReusableResumeBullet] = Field(default_factory=list)


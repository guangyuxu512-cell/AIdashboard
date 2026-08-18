"""Skill implementations are deferred until the skill contract is defined."""
from app.skills.registry import SkillDefinition, SkillRegistry, registry
from app.skills import system as _system
from app.skills import yingdao as _yingdao


__all__ = ["SkillDefinition", "SkillRegistry", "registry"]

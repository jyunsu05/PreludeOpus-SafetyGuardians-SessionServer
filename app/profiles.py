EDUCATION_RULES = {
    "guidesEnabled": True,
    "voiceEnabled": True,
    "sopLockEnabled": True,
    "violationsRecorded": True,
    "violationsBlockProgress": True,
    "timeLimitSec": None,
    "allowSkip": False,
    "requireTraineeId": True,
    "passedRequiresDecon": False,
}

EXPERIENCE_RULES = {
    "guidesEnabled": True,
    "voiceEnabled": False,
    "sopLockEnabled": False,
    "violationsRecorded": True,
    "violationsBlockProgress": False,
    "timeLimitSec": 600,
    "allowSkip": False,
    "requireTraineeId": False,
    "passedRequiresDecon": False,
}

EDUCATION_UPLOAD = {
    "eventsIntervalSec": 15,
    "flushOnPhaseComplete": True,
    "offlineQueue": True,
    "heartbeatIntervalSec": 0,
}

EXPERIENCE_UPLOAD = {
    "eventsIntervalSec": 20,
    "flushOnPhaseComplete": True,
    "offlineQueue": True,
    "heartbeatIntervalSec": 20,
}


def profile_for(mode: str) -> tuple[dict, dict]:
    if mode == "experience":
        return EXPERIENCE_RULES, EXPERIENCE_UPLOAD
    return EDUCATION_RULES, EDUCATION_UPLOAD

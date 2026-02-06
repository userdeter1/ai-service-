"""
Entity Extractor - Multilingual Entity Extraction

Extract structured entities from natural language messages.
Supports French and English patterns with conservative extraction (no hallucination).

Extracted entities:
- booking_ref: Booking references (REF123, BK12345, etc.)
- carrier_id: Carrier/company IDs (numbers)
- terminal: Terminal identifiers (A, B, C, etc.)
- gate: Gate identifiers (G1, G2, porte 3, etc.)
- date signals: today/tomorrow/yesterday + explicit dates
- requested_time: Time specifications (HH:MM)
- plate: License plate numbers
"""

import re
import logging
from typing import Dict, Any, List, Optional
from datetime import date, timedelta

logger = logging.getLogger(__name__)


# ============================================================================
# Entity Patterns (Multilingual FR/EN)
# ============================================================================

# Booking reference patterns
BOOKING_REF_PATTERNS = [
    # Standard: REF123, REF-123, ref123
    r"\b(REF|ref|Ref)[-\s]?(\d{3,})\b",
    # Booking variants: BK12345, BOOK123
    r"\b(BK|bk|BOOK|book|booking|réservation)[-\s]?(\d{4,})\b",
    # Contextual: "booking 12345", "reference 456"
    r"\b(booking|reference|réservation|référence)\s+(\d{5,})\b",
]

# Carrier ID patterns
CARRIER_ID_PATTERNS = [
    # "carrier 123", "transporteur 456"
    r"\b(carrier|transporteur|chauffeur|driver|company|société|entreprise)\s+(?:id\s+)?(\d+)\b",
    # "ID 77" (standalone)
    r"\bID\s+(\d+)\b",
    # "for 123", "rate 456" (context dependent)
    r"\b(for|rate|score|pour|noter)\s+(\d{2,})\b",
]

# Terminal patterns
TERMINAL_PATTERNS = [
    # EN: "terminal A", "Terminal B"
    r"\b(terminal)\s+([A-Z])\b",
    # FR: "terminale A", "au terminal B"
    r"\b(terminale?|au\s+terminal)\s+([A-Z])\b",
]

# Gate patterns
GATE_PATTERNS = [
    # EN: "gate 3", "Gate 2"
    r"\b(gate)\s+([A-Z]?\d+)\b",
    # FR: "porte 3"
    r"\b(porte)\s+(\d+)\b",
    # Compact: "G2", "G12"
    r"\b(G)(\d+)\b",
]

# Date patterns
DATE_PATTERNS = {
    "date_today": [
        r"\b(today|now|current|aujourd'hui|maintenant)\b",
    ],
    "date_tomorrow": [
        r"\b(tomorrow|next day|demain|lendemain)\b",
    ],
    "date_yesterday": [
        r"\b(yesterday|last day|hier)\b",
    ],
    "date_explicit": [
        # YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY
        r"\b(\d{4}[-/]\d{2}[-/]\d{2})\b",
        r"\b(\d{2}[-/]\d{2}[-/]\d{4})\b",
    ],
}

# Time patterns
TIME_PATTERNS = [
    # HH:MM, HH:MM:SS
    r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b",
    # "at 9am", "à 14h"
    r"\bat\s+(\d{1,2})\s*(am|pm|h)\b",
    r"\bà\s+(\d{1,2})\s*h\b",
]

# Plate patterns (license plates)
PLATE_PATTERNS = [
    # ABC123, AB-1234-CD
    r"\b([A-Z]{1,3}[-\s]?\d{3,4}[-\s]?[A-Z]{0,3})\b",
]


# ============================================================================
# Entity Extraction Functions
# ============================================================================

def extract_entities(
    message: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Extract entities from message with multilingual support.
    
    Conservative extraction - never hallucinates entities.
    
    Args:
        message: User message
        context: Additional context (intent, previous entities, etc.)
    
    Returns:
        Dictionary of extracted entities
    """
    if not message or not message.strip():
        return {}
    
    entities: Dict[str, Any] = {}
    
    # Extract booking references
    booking_refs = _extract_booking_refs(message)
    if booking_refs:
        entities["booking_ref"] = booking_refs[0] if len(booking_refs) == 1 else booking_refs
    
    # Extract carrier IDs
    carrier_id = _extract_carrier_id(message)
    if carrier_id:
        entities["carrier_id"] = carrier_id
    
    # Extract terminal
    terminal = _extract_terminal(message)
    if terminal:
        entities["terminal"] = terminal
    
    # Extract gate
    gate = _extract_gate(message)
    if gate:
        entities["gate"] = gate
    
    # Extract date signals
    date_entities = _extract_date_signals(message)
    entities.update(date_entities)
    
    # Extract time
    requested_time = _extract_time(message, date_entities)
    if requested_time:
        entities["requested_time"] = requested_time
    
    # Extract plate (optional)
    plate = _extract_plate(message)
    if plate:
        entities["plate"] = plate
    
    logger.debug(f"Extracted {len(entities)} entities from message")
    
    return entities


def _extract_booking_refs(message: str) -> List[str]:
    """Extract booking references (supports multiple)."""
    refs = []
    seen = set()
    
    for pattern in BOOKING_REF_PATTERNS:
        for match in re.finditer(pattern, message, re.IGNORECASE):
            if len(match.groups()) >= 2:
                prefix = match.group(1).upper()
                digits = match.group(2)
                
                # Normalize: REF + digits
                if prefix in ("REF", "BK", "BOOK"):
                    ref = f"{prefix}{digits}"
                else:
                    ref = f"REF{digits}"
                
                # Deduplicate
                if ref not in seen:
                    refs.append(ref)
                    seen.add(ref)
            elif len(match.groups()) == 1:
                # Standalone number
                digits = match.group(1)
                ref = f"REF{digits}"
                if ref not in seen:
                    refs.append(ref)
                    seen.add(ref)
    
    return refs


def _extract_carrier_id(message: str) -> Optional[str]:
    """Extract carrier/company ID (returns first found)."""
    for pattern in CARRIER_ID_PATTERNS:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            if len(match.groups()) >= 2:
                carrier_id = match.group(2)
            else:
                carrier_id = match.group(1)
            
            # Validate: must be numeric and reasonable length
            if carrier_id.isdigit() and 1 <= len(carrier_id) <= 10:
                return carrier_id
    
    return None


def _extract_terminal(message: str) -> Optional[str]:
    """Extract terminal identifier."""
    for pattern in TERMINAL_PATTERNS:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            if len(match.groups()) >= 2:
                terminal = match.group(2).upper()
            else:
                terminal = match.group(1).upper()
            
            # Validate: single letter or number
            if len(terminal) == 1 and terminal.isalnum():
                return terminal
    
    return None


def _extract_gate(message: str) -> Optional[str]:
    """Extract gate identifier, normalized as G{number}."""
    for pattern in GATE_PATTERNS:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            if len(match.groups()) >= 2:
                gate_num = match.group(2)
            else:
                gate_num = match.group(1)
            
            # Normalize to G{number}
            gate_num = re.sub(r"[^\d]", "", gate_num)  # Extract digits only
            if gate_num and gate_num.isdigit():
                return f"G{gate_num}"
    
    return None


def _extract_date_signals(message: str) -> Dict[str, Any]:
    """Extract date signals (today/tomorrow/yesterday/explicit)."""
    entities = {}
    
    # Check keyword dates
    for date_key, patterns in DATE_PATTERNS.items():
        if date_key.startswith("date_") and date_key != "date_explicit":
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    entities[date_key] = True
                    break
    
    # Check explicit dates
    for pattern in DATE_PATTERNS["date_explicit"]:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            date_str = match.group(1)
            # Try to parse and normalize to YYYY-MM-DD
            normalized = _normalize_date(date_str)
            if normalized:
                entities["date"] = normalized
                break
    
    return entities


def _normalize_date(date_str: str) -> Optional[str]:
    """Normalize date string to YYYY-MM-DD format."""
    # Already in YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    
    # Convert DD/MM/YYYY or DD-MM-YYYY to YYYY-MM-DD
    match = re.match(r"^(\d{2})[-/](\d{2})[-/](\d{4})$", date_str)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    
    # Convert YYYY/MM/DD to YYYY-MM-DD
    date_str = date_str.replace("/", "-")
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
    
    return None


def _extract_time(message: str, date_entities: Dict[str, Any]) -> Optional[str]:
    """Extract requested time, combined with date if available."""
    for pattern in TIME_PATTERNS:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            # HH:MM format
            if len(groups) >= 2 and groups[0] and groups[1]:
                hour = groups[0]
                minute = groups[1]
                
                # Validate
                try:
                    h = int(hour)
                    m = int(minute)
                    if 0 <= h <= 23 and 0 <= m <= 59:
                        time_str = f"{h:02d}:{m:02d}:00"
                        
                        # Combine with date if available
                        if "date" in date_entities:
                            return f"{date_entities['date']} {time_str}"
                        elif date_entities.get("date_today"):
                            return f"{date.today().isoformat()} {time_str}"
                        elif date_entities.get("date_tomorrow"):
                            return f"{(date.today() + timedelta(days=1)).isoformat()} {time_str}"
                        elif date_entities.get("date_yesterday"):
                            return f"{(date.today() - timedelta(days=1)).isoformat()} {time_str}"
                        else:
                            return time_str
                except ValueError:
                    continue
            
            # "at 9am" / "à 14h" format
            elif len(groups) >= 2 and groups[0]:
                hour = groups[0]
                modifier = groups[1].lower() if len(groups) > 1 and groups[1] else ""
                
                try:
                    h = int(hour)
                    
                    # Handle am/pm
                    if modifier == "pm" and h < 12:
                        h += 12
                    elif modifier == "am" and h == 12:
                        h = 0
                    
                    if 0 <= h <= 23:
                        time_str = f"{h:02d}:00:00"
                        
                        # Combine with date
                        if "date" in date_entities:
                            return f"{date_entities['date']} {time_str}"
                        elif date_entities.get("date_today"):
                            return f"{date.today().isoformat()} {time_str}"
                        elif date_entities.get("date_tomorrow"):
                            return f"{(date.today() + timedelta(days=1)).isoformat()} {time_str}"
                        else:
                            return time_str
                except ValueError:
                    continue
    
    return None


def _extract_plate(message: str) -> Optional[str]:
    """Extract license plate number."""
    for pattern in PLATE_PATTERNS:
        match = re.search(pattern, message)
        if match:
            plate = match.group(1).strip()
            # Remove spaces/hyphens for normalization, then re-add standard format
            plate_clean = re.sub(r"[-\s]", "", plate)
            
            # Basic validation: must have both letters and digits
            if re.search(r"[A-Z]", plate_clean) and re.search(r"\d", plate_clean):
                return plate
    
    return None


# ============================================================================
# Self-Test (run with: python -m app.orchestrator.entity_extractor)
# ============================================================================

if __name__ == "__main__":
    print("Entity Extractor - Self Test\n" + "=" * 70)
    
    test_cases = [
        # Booking refs
        ("What's the status of REF123?", {"booking_ref": "REF123"}),
        ("Check REF-456 and BK7890", {"booking_ref": ["REF456", "BK7890"]}),
        ("Booking 12345 status", {"booking_ref": "REF12345"}),
        
        # Carrier IDs
        ("Score for carrier 123", {"carrier_id": "123"}),
        ("Transporteur 456 performance", {"carrier_id": "456"}),
        ("Rate ID 77", {"carrier_id": "77"}),
        
        # Terminals
        ("Available slots at terminal A", {"terminal": "A"}),
        ("Terminale B availability", {"terminal": "B"}),
        
        # Gates
        ("Check gate 3", {"gate": "G3"}),
        ("Porte 12 status", {"gate": "G12"}),
        ("At G5", {"gate": "G5"}),
        
        # Dates
        ("Show today's slots", {"date_today": True}),
        ("Tomorrow at terminal A", {"date_tomorrow": True}),
        ("Yesterday's passages", {"date_yesterday": True}),
        ("Availability on 2026-02-05", {"date": "2026-02-05"}),
        
        # Times
        ("Book at 14:30", {"requested_time": "14:30:00"}),
        ("Slot at 9am tomorrow", {"date_tomorrow": True, "requested_time": "09:00:00"}),
        
        # Complex
        ("REF123 status at terminal A gate 2 tomorrow at 14:00", {
            "booking_ref": "REF123",
            "terminal": "A",
            "gate": "G2",
            "date_tomorrow": True,
            "requested_time": "14:00:00"
        }),
    ]
    
    passed = 0
    failed = 0
    
    for message, expected in test_cases:
        result = extract_entities(message)
        
        # Check if all expected entities are present
        all_match = True
        for key, value in expected.items():
            if key not in result:
                all_match = False
                break
            if result[key] != value:
                all_match = False
                break
        
        status = "✓" if all_match else "✗"
        
        if all_match:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} '{message[:50]:50s}'")
        if not all_match:
            print(f"  Expected: {expected}")
            print(f"  Got:      {result}")
    
    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed ({passed/(passed+failed)*100:.1f}% accuracy)")

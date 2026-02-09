import logging
from itertools import combinations
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime
import math
from .database import Request
from .config import settings

logger = logging.getLogger(__name__)

def find_match_for_requests(requests: List[Request]) -> Optional[List[Request]]:
    """
    Finds a subset of requests that sum to 10 hours.
    Prioritizes:
    1. Older requests (FIFO) - handled by sorting input requests by created_at
    2. Larger groups (4 people > 3 > 2) - handled by checking k=4,3,2
    3. Range feasibility - checks if 10 is within [sum(min), sum(max)]
    """
    if not requests:
        logger.warning("find_match_for_requests called with empty request list")
        return None
    
    # Validate request data
    for req in requests:
        if req.min_hours is None or req.max_hours is None:
            logger.error(f"Request {req.id} has invalid hours: min={req.min_hours}, max={req.max_hours}")
            continue
        if req.min_hours < 0 or req.max_hours < 0:
            logger.warning(f"Request {req.id} has negative hours: min={req.min_hours}, max={req.max_hours}")
        if req.min_hours > req.max_hours:
            logger.warning(f"Request {req.id} has min_hours > max_hours: {req.min_hours} > {req.max_hours}")
    
    # Try group sizes from 4 down to 2
    for k in range(4, 1, -1):
        # combinations will produce groups using earlier elements (older requests) first
        for group in combinations(requests, k):
            min_sum = sum(r.min_hours for r in group)
            max_sum = sum(r.max_hours for r in group)
            
            # Check if 10 hours falls within the combined range
            # Using tolerance for float comparison
            if min_sum <= 10.0 + 1e-5 and max_sum >= 10.0 - 1e-5:
                logger.info(f"Match found: {len(group)} users, hours range [{min_sum:.1f}-{max_sum:.1f}]")
                return list(group)
    return None

def check_and_process_matches(db: Session) -> Optional[List[Request]]:
    """
    Queries the database for pending requests where target_date <= today.
    If a match is found, updates their status to 'matched' and returns the list.
    """
    today = datetime.now(settings.tz).date()
    
    try:
        # Query: Requests for target_date <= today OR target_date is NULL (Anytime)
        # And status is 'pending'
        # Order by created_at ASC for FIFO
        query = db.query(Request).filter(
            Request.status == 'pending',
            or_(Request.target_date <= today, Request.target_date == None)
        ).order_by(Request.created_at.asc())
        
        candidates = query.all()
    except SQLAlchemyError as e:
        logger.error(f"Database error while querying pending requests: {e}")
        return None
    
    if not candidates:
        logger.info("No pending requests found for matching")
        return None
    
    logger.info(f"Found {len(candidates)} candidate requests for matching")

    match = find_match_for_requests(candidates)
    
    if match:
        # Mark as matched
        try:
            for req in match:
                req.status = 'matched'
            db.commit()
            logger.info(f"Successfully marked {len(match)} requests as matched")
            return match
        except SQLAlchemyError as e:
            logger.error(f"Database error while updating request status to 'matched': {e}")
            db.rollback()
            return None
        
    return None

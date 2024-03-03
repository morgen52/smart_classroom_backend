from datetime import datetime

# "%Y-%m-%d-%H:%M:%S.%f"
# threshold in seconds
def timestamp_cmp(timestamp1, timestamp2, threshold=0.5):
    """
    Compare two timestamps and return True if they are within the threshold (in seconds)
    """
    timestamp1 = datetime.strptime(timestamp1, "%Y-%m-%d-%H:%M:%S.%f")
    timestamp2 = datetime.strptime(timestamp2, "%Y-%m-%d-%H:%M:%S.%f")
    difference = abs((timestamp2 - timestamp1).total_seconds())
    if difference <= threshold:
        return "equal"
    elif timestamp1 < timestamp2:
        return "less"
    else:
        return "greater"

    
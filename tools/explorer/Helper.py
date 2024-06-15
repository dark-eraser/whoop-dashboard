import os

def helper_milliseconds_to_hours(millis):
    return millis / 1000 / 60 / 60
def helper_milliseconds_to_hours_minutes(milliseconds):
    # Total seconds from milliseconds
    total_seconds = milliseconds / 1000
    # Calculate hours
    hours = int(total_seconds // 3600)
    # Calculate remaining minutes
    minutes = int((total_seconds % 3600) // 60)
    return hours, minutes

def helper_delta_percentage(old_value, new_value):
    percentage_change = ((new_value - old_value) / old_value) * 100
    return percentage_change

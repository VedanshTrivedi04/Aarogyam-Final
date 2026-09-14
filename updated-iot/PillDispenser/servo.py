from machine import Pin, PWM

from config import (
    SERVO_PIN,
    SERVO_CLOSED_ANGLE,
    SERVO_OPEN_ANGLE
)


# ============================================================
# SERVO
# ============================================================

servo = PWM(
    Pin(SERVO_PIN),
    freq=50
)


# ============================================================
# SET ANGLE
# ============================================================

def set_angle(angle):

    if angle < 0:

        angle = 0


    if angle > 180:

        angle = 180


    duty = int(
        1638
        +
        (angle / 180)
        *
        (8192 - 1638)
    )


    servo.duty_u16(duty)


# ============================================================
# OPEN
# ============================================================

def open_servo():

    set_angle(
        SERVO_OPEN_ANGLE
    )

    print("LID OPEN")


# ============================================================
# CLOSE
# ============================================================

def close_servo():

    set_angle(
        SERVO_CLOSED_ANGLE
    )

    print("LID CLOSED")
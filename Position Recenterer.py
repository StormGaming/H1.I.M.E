import win32com.client


def connect_to_mount(progid):
    telescope = win32com.client.Dispatch(progid)
    telescope.Connected = True
    if telescope.Connected:
        print(f"Connected to {telescope.Name}")
    return telescope


def slew_to(telescope, ra, dec):
    telescope.TargetRightAscension = ra
    telescope.TargetDeclination = dec
    telescope.SlewToTarget()


def get_current_position(telescope):
    current_ra = telescope.RightAscension
    current_dec = telescope.Declination
    return current_ra, current_dec


def get_slew_speed(telescope):
    # SlewSettleTime is used here as an example. It may be different depending on the driver.
    slew_speed = telescope.SlewSettleTime
    return slew_speed


# Usage example
scope = connect_to_mount("EQMOD.Telescope")
slew_to(scope, 0, 0)  # RA and Dec need to be set correctly

current_ra, current_dec = get_current_position(scope)
print(f"Current Position - RA: {current_ra}, Dec: {current_dec}")

slew_speed = get_slew_speed(scope)
print(f"Slew Speed: {slew_speed}")

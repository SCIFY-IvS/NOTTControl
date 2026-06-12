import numpy as np
import matplotlib.pyplot as plt

# ============================================================
# USER PARAMETERS
# ============================================================

# Wavelength range [micron]
lam_min = 3.440
lam_max = 4.075
n_points = 500

# Prism parameters
A_deg = 60.0          # Apex angle of equilateral prism [deg]
i1_deg = 35.0         # Incidence angle at first face, wrt first-face normal [deg]

# Camera /detetor parameters
f_mm = 50.0           # Focal length [mm]
pixel_pitch_um = 15.0 # Pixel pitch [micron]
p0 = 250.0           # Reference pixel 
theta_cam_deg = -30.0  # Camera optical axis angle wrt horizontal [deg]

# Sign convention:
sign_out = -1 

# this chooses which angular sign convention matches the detector ordering and camera-angle definition in the simplified model.
# in addition, we choose the incoming horizontal ray to be 0 degrees, i.e,  Incoming beam taken as theta_in = 0

# ============================================================
# SELLMEIER EQUATION FOR CaF2
# lambda in microns
# n^2 - 1 = 0.33973
#          + 0.69913 * lambda^2 / (lambda^2 - 0.09374^2)
#          + 0.11994 * lambda^2 / (lambda^2 - 21.18^2)
#          + 4.35181 * lambda^2 / (lambda^2 - 38.46^2)
# ============================================================

def n_caf2(lambda_um):
    lam2 = lambda_um**2
    n2_minus_1 = (
        0.33973
        + (0.69913 * lam2) / (lam2 - 0.09374**2)
        + (0.11994 * lam2) / (lam2 - 21.18**2)
        + (4.35181 * lam2) / (lam2 - 38.46**2)
    )
    return np.sqrt(1.0 + n2_minus_1)

# ============================================================
# PRISM MODEL USING SNELL'S LAW
# All angles internally in radians
# ============================================================

def prism_model(lambda_um, A_deg, i1_deg, f_mm, pixel_pitch_um, p0, theta_cam_deg, sign_out=+1):
    A = np.deg2rad(A_deg)
    i1 = np.deg2rad(i1_deg)
    theta_cam = np.deg2rad(theta_cam_deg)
    pixel_pitch_mm = pixel_pitch_um / 1000.0

    n = n_caf2(lambda_um)

    # First refraction
    r1 = np.arcsin(np.sin(i1) / n)

    # Inside prism
    r2 = A - r1

    # Emergence angle wrt second-face normal
    e2 = np.arcsin(n * np.sin(r2))

    # Total deviation
    delta = i1 + e2 - A

    # delta is the deviation magnitude 
    # sign_out sets the lab-frame sign convention for the emergent ray
    # in this simplified 2D model.  
    theta_out = sign_out * delta

    # Angle of ray relative to camera optical axis
    delta_theta = theta_out - theta_cam

    # Position in focal plane [mm]
    y_mm = f_mm * np.tan(delta_theta)

    # Convert to detector pixel
    pixel = p0 + y_mm / pixel_pitch_mm

    return {
        "lambda_um": lambda_um,
        "n": n,
        "r1_rad": r1,
        "r2_rad": r2,
        "e2_rad": e2,
        "delta_rad": delta,
        "theta_out_rad": theta_out,
        "y_mm": y_mm,
        "pixel": pixel,
    }

# ============================================================
# RUN MODEL AND RETURN OUTPUT
# ============================================================

def run_analytical_solution(
    lam_min=lam_min,
    lam_max=lam_max,
    n_points=n_points,
    A_deg=A_deg,
    i1_deg=i1_deg,
    f_mm=f_mm,
    pixel_pitch_um=pixel_pitch_um,
    p0=p0,
    theta_cam_deg=theta_cam_deg,
    sign_out=sign_out,
):
    lam = np.linspace(lam_min, lam_max, n_points)

    result = prism_model(
        lambda_um=lam,
        A_deg=A_deg,
        i1_deg=i1_deg,
        f_mm=f_mm,
        pixel_pitch_um=pixel_pitch_um,
        p0=p0,
        theta_cam_deg=theta_cam_deg,
        sign_out=sign_out,
    )

    n_vals = result["n"]
    y_mm = result["y_mm"]
    pixel = result["pixel"]
    theta_out_deg = np.rad2deg(result["theta_out_rad"])
    delta_deg = np.rad2deg(result["delta_rad"])

    return {
        "lam": lam,
        "n_vals": n_vals,
        "y_mm": y_mm,
        "pixel": pixel,
        "theta_out_deg": theta_out_deg,
        "delta_deg": delta_deg
    }


if __name__ == "__main__":
    out = run_analytical_solution(
        lam_min=lam_min,
        lam_max=lam_max,
        n_points=n_points,
        A_deg=A_deg,
        i1_deg=i1_deg,
        f_mm=f_mm,
        pixel_pitch_um=pixel_pitch_um,
        p0=p0,
        theta_cam_deg=theta_cam_deg,
        sign_out=sign_out,
    )

    lam = out["lam"]
    n_vals = out["n_vals"]
    y_mm = out["y_mm"]
    pixel = out["pixel"]
    theta_out_deg = out["theta_out_deg"]
    delta_deg = out["delta_deg"]

    print("=== Basic output ===")
    print(f"lambda range: {lam[0]:.3f} to {lam[-1]:.3f} micron")
    print(f"n(lambda) range: {n_vals[0]:.6f} to {n_vals[-1]:.6f}")
    print(f"theta_out range: {theta_out_deg[0]:.3f} to {theta_out_deg[-1]:.3f} deg")
    print(f"pixel range: {pixel[0]:.2f} to {pixel[-1]:.2f}")
    print(f"total span: {abs(pixel[-1] - pixel[0]):.2f} pixels")

    # ============================================================
    # PLOTS
    # ============================================================

    plt.figure(figsize=(7, 5))
    plt.plot(lam, pixel)
    plt.xlabel("Wavelength [micron]")
    plt.ylabel("Predicted pixel position")
    plt.title("Prism spectrograph wavelength solution")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(7, 5))
    plt.plot(lam, n_vals)
    plt.xlabel("Wavelength [micron]")
    plt.ylabel("Refractive index n")
    plt.title("CaF2 refractive index from Sellmeier equation")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(7, 5))
    plt.plot(lam, theta_out_deg)
    plt.xlabel("Wavelength [micron]")
    plt.ylabel("Emergent angle [deg]")
    plt.title("Emergent angle vs wavelength")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # ============================================================
    # OPTIONAL: LINEAR DISPERSION dy/dlambda
    # ============================================================

    dy_dlambda_mm_per_um = np.gradient(y_mm, lam)
    dp_dlambda_pix_per_um = np.gradient(pixel, lam)

    print("\n=== Linear dispersion ===")
    print(f"Mean dy/dlambda = {np.mean(dy_dlambda_mm_per_um):.4f} mm/micron")
    print(f"Mean dp/dlambda = {np.mean(dp_dlambda_pix_per_um):.2f} pix/micron")

    plt.figure(figsize=(7, 5))
    plt.plot(lam, dy_dlambda_mm_per_um)
    plt.xlabel("Wavelength [micron]")
    plt.ylabel("dy/dlambda [mm / micron]")
    plt.title("Linear dispersion")
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # plt.figure(figsize=(7, 5))
    # plt.plot(lam, dp_dlambda_pix_per_um)
    # plt.xlabel("Wavelength [micron]")
    # plt.ylabel("dp/dlambda [pix / micron]")
    # plt.title("Pixel dispersion")
    # plt.grid(True)
    # plt.tight_layout()
    # plt.show()
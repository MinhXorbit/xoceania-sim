"""Bird-Hulstrom (1981) clear-sky solar irradiance model.

Computes global, direct, and diffuse irradiance (W/m²) as a function of latitude,
longitude, day of year, and local hour. Includes cloud-cover correction (Kasten-Czeplak
1980) and Beer-Lambert underwater PAR attenuation.

References:
    Bird, R.E. & Hulstrom, R.L. (1981). A simplified clear sky model for direct and
        diffuse insolation on horizontal surfaces. SERI/TR-642-761. Solar Energy
        Research Institute, Golden, CO.
    Kasten, F. & Czeplak, G. (1980). Solar and terrestrial radiation dependent on the
        amount and type of cloud. Solar Energy, 24, 177-189.
    Morel, A. & Smith, R.C. (1974). Relation between total quanta and total energy
        for aquatic photosynthesis. Limnology and Oceanography, 19, 591-600.
    Weiskerger, C.J. et al. (2018). Effect of solar radiation on the attenuation of
        light in shallow eutrophic waters. Water Resources Research.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class IrradianceResult(NamedTuple):
    """Solar irradiance components at a given location and time.

    Attributes:
        I_global: Global horizontal irradiance (W/m²).
        I_direct: Direct normal irradiance on horizontal surface (W/m²).
        I_diffuse: Diffuse horizontal irradiance (W/m²).
        I_par: Photosynthetically active radiation at surface (W/m²).
        I_par_z: Depth-averaged PAR (W/m²) integrated via Beer-Lambert.
        cos_sza: Cosine of solar zenith angle.
    """

    I_global: float
    I_direct: float
    I_diffuse: float
    I_par: float
    I_par_z: float
    cos_sza: float


def _solar_declination(doy: int) -> float:
    """Compute solar declination angle (radians) from day of year.

    Uses Spencer (1971) approximation, accurate to ±0.01°.

    Args:
        doy: Day of year (1-365).

    Returns:
        Solar declination in radians.
    """
    B = 2.0 * math.pi * (doy - 1) / 365.0
    decl = (
        0.006918
        - 0.399912 * math.cos(B)
        + 0.070257 * math.sin(B)
        - 0.006758 * math.cos(2 * B)
        + 0.000907 * math.sin(2 * B)
        - 0.002697 * math.cos(3 * B)
        + 0.001480 * math.sin(3 * B)
    )
    return decl


def _equation_of_time(doy: int) -> float:
    """Compute equation of time correction (hours).

    Args:
        doy: Day of year (1-365).

    Returns:
        Time correction in hours.
    """
    B = 2.0 * math.pi * (doy - 80) / 365.0
    eot = 9.87 * math.sin(2 * B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)
    return eot / 60.0  # convert minutes → hours


def _cos_zenith(lat_rad: float, decl: float, hour_angle_rad: float) -> float:
    """Compute cosine of solar zenith angle.

    Args:
        lat_rad: Latitude in radians.
        decl: Solar declination in radians.
        hour_angle_rad: Hour angle in radians.

    Returns:
        cos(SZA), clamped to [0, 1].
    """
    cos_sza = (
        math.sin(lat_rad) * math.sin(decl)
        + math.cos(lat_rad) * math.cos(decl) * math.cos(hour_angle_rad)
    )
    return max(0.0, cos_sza)


def _extraterrestrial_irradiance(doy: int) -> float:
    """Compute extraterrestrial solar irradiance (W/m²) correcting for Earth-Sun distance.

    Args:
        doy: Day of year.

    Returns:
        Extraterrestrial irradiance (W/m²). Solar constant = 1367 W/m².
    """
    # Earth-Sun distance correction factor (Spencer 1971)
    B = 2.0 * math.pi * (doy - 1) / 365.0
    E0 = (
        1.000110
        + 0.034221 * math.cos(B)
        + 0.001280 * math.sin(B)
        + 0.000719 * math.cos(2 * B)
        + 0.000077 * math.sin(2 * B)
    )
    return 1367.0 * E0  # W/m²


def bird_hulstrom_irradiance(
    lat_deg: float,
    lon_deg: float,
    doy: int,
    hour_utc: float,
    altitude_m: float = 0.0,
    precipitable_water_cm: float = 2.0,
    aerosol_optical_depth: float = 0.1,
    ozone_cm: float = 0.35,
) -> tuple[float, float, float]:
    """Bird-Hulstrom (1981) clear-sky direct and diffuse irradiance.

    Computes beam (direct) and diffuse irradiance on a horizontal surface using
    atmospheric transmittance factors for Rayleigh scattering, ozone absorption,
    water vapor absorption, and aerosol extinction.

    Args:
        lat_deg: Latitude (degrees N, positive north).
        lon_deg: Longitude (degrees E, positive east).
        doy: Day of year (1-365).
        hour_utc: UTC hour (0-24, fractional allowed).
        altitude_m: Site altitude above sea level (m). Default 0 (sea level).
        precipitable_water_cm: Precipitable water vapor (cm). Default 2.0 cm.
        aerosol_optical_depth: Aerosol optical depth at 500 nm. Default 0.1.
        ozone_cm: Total column ozone (cm-atm). Default 0.35.

    Returns:
        Tuple of (I_direct, I_diffuse, I_global) in W/m².

    References:
        Bird & Hulstrom (1981), SERI/TR-642-761.
    """
    lat_rad = math.radians(lat_deg)
    decl = _solar_declination(doy)
    eot = _equation_of_time(doy)

    # Solar time correction: local standard meridian offset
    lon_std = round(lon_deg / 15.0) * 15.0
    time_correction = 4.0 * (lon_deg - lon_std) / 60.0 + eot  # hours
    solar_hour = hour_utc + time_correction + lon_deg / 15.0
    # Hour angle (rad): noon = 0
    hour_angle_rad = math.radians((solar_hour - 12.0) * 15.0)

    cos_sza = _cos_zenith(lat_rad, decl, hour_angle_rad)
    if cos_sza <= 0.0:
        return 0.0, 0.0, 0.0

    I0 = _extraterrestrial_irradiance(doy)
    # Pressure correction for altitude
    pressure_ratio = math.exp(-altitude_m / 8434.5)

    # Air mass (Kasten & Young 1989 formula for accuracy at low elevations)
    sza_rad = math.acos(cos_sza)
    sza_deg = math.degrees(sza_rad)
    if sza_deg < 89.0:
        am = 1.0 / (cos_sza + 0.50572 * (96.07995 - sza_deg) ** (-1.6364))
    else:
        am = 38.0  # near-horizon limit
    am_p = am * pressure_ratio  # pressure-corrected air mass

    # Rayleigh scattering transmittance (Bird & Hulstrom 1981, Eq. 8)
    T_r = math.exp(-0.0903 * am_p**0.84 * (1.0 + am_p - am_p**1.01))

    # Ozone transmittance (Bird & Hulstrom 1981)
    u3 = ozone_cm * am
    T_oz = 1.0 - 0.1611 * u3 * (1.0 + 139.48 * u3) ** (-0.3035) - 0.002715 * u3 / (
        1.0 + 0.044 * u3 + 0.0003 * u3**2
    )

    # Water vapor transmittance
    u1 = precipitable_water_cm * am
    T_wv = 1.0 - 2.4959 * u1 / ((1.0 + 79.034 * u1) ** 0.6828 + 6.385 * u1)

    # Aerosol transmittance (simplified two-term approximation)
    tau_a = aerosol_optical_depth  # at 500 nm
    T_as = math.exp(-tau_a * am)
    # Aerosol absorptance ≈ 0 for standard rural aerosol (omega0 ≈ 0.945)
    T_aa = 1.0 - 0.1 * (1.0 - am + am**1.06) * (1.0 - T_as)
    T_a = T_as * T_aa

    # Direct beam on horizontal surface
    I_direct = 0.9662 * I0 * cos_sza * T_r * T_oz * T_wv * T_a

    # Diffuse irradiance (Bird & Hulstrom 1981, Eq. 24-26)
    cs = 0.26  # forward scattering fraction
    I_ra = 0.79 * I0 * cos_sza * T_oz * T_wv * T_aa * (0.5 * (1.0 - T_r)) / (
        1.0 - am + am**1.02
    )
    I_diff_a = 0.79 * I0 * cos_sza * T_oz * T_wv * T_aa * T_r * cs * (
        1.0 - T_as
    ) / (1.0 - am + am**1.02)
    albedo_g = 0.2  # ground/pond albedo for diffuse correction
    albedo_sky = 0.0685  # sky albedo
    I_diffuse = (I_ra + I_diff_a) / (1.0 - albedo_g * albedo_sky)

    I_global = I_direct + I_diffuse

    return max(0.0, I_direct), max(0.0, I_diffuse), max(0.0, I_global)


def kasten_czeplak_correction(I_clear: float, cloud_cover: float) -> float:
    """Apply Kasten-Czeplak (1980) cloud-cover correction to clear-sky irradiance.

    Reduces clear-sky irradiance based on fractional cloud cover.

    Args:
        I_clear: Clear-sky global irradiance (W/m²).
        cloud_cover: Cloud cover fraction (0=clear, 1=overcast).

    Returns:
        Cloud-corrected irradiance (W/m²).

    References:
        Kasten, F. & Czeplak, G. (1980). Solar and terrestrial radiation dependent
        on the amount and type of cloud. Solar Energy, 24, 177-189.
    """
    # Empirical Kasten-Czeplak formula: I = I0 * (1 - 0.75 * c^3.4)
    return I_clear * (1.0 - 0.75 * cloud_cover**3.4)


def clear_sky_irradiance(
    lat_deg: float,
    lon_deg: float,
    doy: int,
    hour_utc: float,
    cloud_cover: float = 0.0,
    **kwargs: float,
) -> IrradianceResult:
    """Compute cloud-corrected solar irradiance components.

    Combines Bird-Hulstrom clear-sky model with Kasten-Czeplak cloud correction.

    Args:
        lat_deg: Latitude (degrees N).
        lon_deg: Longitude (degrees E).
        doy: Day of year (1-365).
        hour_utc: UTC hour (0-24).
        cloud_cover: Cloud cover fraction (0-1). Default 0 (clear sky).
        **kwargs: Additional arguments passed to bird_hulstrom_irradiance.

    Returns:
        IrradianceResult namedtuple with all irradiance components.
    """
    I_dir, I_dif, I_glo = bird_hulstrom_irradiance(
        lat_deg, lon_deg, doy, hour_utc, **kwargs
    )
    if cloud_cover > 0.0:
        scale = kasten_czeplak_correction(1.0, cloud_cover)
        I_dir *= scale
        I_dif *= scale
        I_glo = I_dir + I_dif

    # Cos zenith for reference
    lat_rad = math.radians(lat_deg)
    decl = _solar_declination(doy)
    eot = _equation_of_time(doy)
    lon_std = round(lon_deg / 15.0) * 15.0
    time_correction = 4.0 * (lon_deg - lon_std) / 60.0 + eot
    solar_hour = hour_utc + time_correction + lon_deg / 15.0
    hour_angle_rad = math.radians((solar_hour - 12.0) * 15.0)
    cos_sza = _cos_zenith(lat_rad, decl, hour_angle_rad)

    # PAR: 0.47 × global shortwave (Morel & Smith 1974)
    I_par = 0.47 * I_glo

    # Depth-integrated PAR stored as surface value; integration done in phytoplankton module
    return IrradianceResult(
        I_global=I_glo,
        I_direct=I_dir,
        I_diffuse=I_dif,
        I_par=I_par,
        I_par_z=I_par,  # surface value; depth correction applied in subsystem
        cos_sza=cos_sza,
    )


def par_underwater(
    I_par_surface: float,
    depth_m: float,
    k_d: float,
) -> float:
    """Compute depth-averaged PAR via Beer-Lambert attenuation.

    Integrates I_PAR from surface to depth H:
        I_avg = I_0 * (1 - exp(-k_d * H)) / (k_d * H)

    Args:
        I_par_surface: Surface PAR (W/m² or μmol photons/m²/s).
        depth_m: Water column depth H (m).
        k_d: Light extinction coefficient (m⁻¹).

    Returns:
        Depth-averaged PAR in same units as I_par_surface.

    References:
        Weiskerger et al. (2018): mean k_d(PAR) = 1.55 m⁻¹ for eutrophic waters.
        Beer-Lambert: I(z) = I_0 * exp(-k_d * z).
    """
    if depth_m <= 0.0 or k_d <= 0.0:
        return I_par_surface
    kH = k_d * depth_m
    if kH < 1e-8:
        return I_par_surface
    return I_par_surface * (1.0 - math.exp(-kH)) / kH

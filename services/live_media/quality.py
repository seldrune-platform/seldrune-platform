from dataclasses import dataclass

@dataclass(frozen=True)
class NetworkSample:
    rtt_ms:int
    packet_loss:float
    available_kbps:int

@dataclass(frozen=True)
class QualityProfile:
    width:int
    height:int
    fps:int
    bitrate_kbps:int

def choose_quality(n:NetworkSample)->QualityProfile:
    if n.packet_loss>=0.08 or n.rtt_ms>=250 or n.available_kbps<900:
        return QualityProfile(640,360,24,650)
    if n.packet_loss>=0.03 or n.rtt_ms>=150 or n.available_kbps<2200:
        return QualityProfile(960,540,30,1400)
    return QualityProfile(1280,720,30,2500)

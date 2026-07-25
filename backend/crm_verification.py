"""Verificação automática de CRM por desafio PDF assinado com ICP-Brasil."""

import base64
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from asn1crypto import core
from cryptography import x509
from cryptography.x509 import ObjectIdentifier
from pyhanko.keys import load_certs_from_pemder_data
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko.sign.validation.status import SignatureCoverageLevel
from pyhanko_certvalidator import ValidationContext
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from backend.settings import setting

CRM_NUMBER_OID = "2.16.76.1.4.2.2.1"
CRM_STATE_OID = "2.16.76.1.4.2.2.2"
ICP_BRASIL_TRUST_LIST_URL = (
    "https://validar.iti.gov.br/trustlist/trust-list-BR.xml"
)
TRUST_LIST_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_CHALLENGE_DURATION_MINUTES = 30
DEFAULT_MAX_SIGNED_PDF_BYTES = 10 * 1024 * 1024

# Pontos de confiança de uso geral publicados na lista oficial do ITI.
# v10 é exclusiva de SSL e v11, de assinatura de código.
OFFICIAL_ROOT_SHA256 = {
    "f0c15afd258fb674e7a96e1a50ff873149364b9ec70d4d93c7a9f1eb6060d020",
    "caa53fc6091c6951887c976e378f6ef89aa6377c55d97b6475422b71ed7e9b17",
    "d8478e37ce19c690cf657381e68fe600e4e1a042536830f06847e03e554c4b01",
}


class CrmVerificationError(Exception):
    """Erro esperado e seguro para exibição ao usuário."""


class CrmVerificationUnavailable(Exception):
    """Falha temporária da infraestrutura de confiança."""


@dataclass(frozen=True)
class ChallengeDocument:
    challenge_id: int
    challenge_code: str
    user_id: int
    account_name: str
    crm: str
    crm_uf: str
    created_at: int
    expires_at: int


@dataclass(frozen=True)
class SignedCrmEvidence:
    certificate_sha256: str
    signed_document_sha256: str


def _integer_setting(
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw_value = setting(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as error:
        raise RuntimeError(f"{name} deve ser um número inteiro.") from error
    if value < minimum or value > maximum:
        raise RuntimeError(
            f"{name} deve estar entre {minimum} e {maximum}."
        )
    return value


def challenge_duration_seconds() -> int:
    minutes = _integer_setting(
        "HEALTHAI_CRM_CHALLENGE_MINUTES",
        DEFAULT_CHALLENGE_DURATION_MINUTES,
        minimum=5,
        maximum=24 * 60,
    )
    return minutes * 60


def max_signed_pdf_bytes() -> int:
    return _integer_setting(
        "HEALTHAI_CRM_PDF_MAX_BYTES",
        DEFAULT_MAX_SIGNED_PDF_BYTES,
        minimum=1024 * 1024,
        maximum=25 * 1024 * 1024,
    )


def revocation_mode() -> str:
    mode = setting("HEALTHAI_CRM_REVOCATION_MODE", "hard-fail").strip().lower()
    if mode not in {"hard-fail", "soft-fail"}:
        raise RuntimeError(
            "HEALTHAI_CRM_REVOCATION_MODE deve ser hard-fail ou soft-fail."
        )
    return mode


def _utc_text(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime(
        "%d/%m/%Y às %H:%M UTC"
    )


def generate_challenge_pdf(challenge: ChallengeDocument) -> bytes:
    """Gera um documento simples e reproduzível, sem armazenar o PDF."""
    output = BytesIO()
    pdf = Canvas(output, pagesize=A4, pageCompression=0)
    width, height = A4
    pdf.setTitle("Desafio de verificação profissional HealthAI")
    pdf.setAuthor("HealthAI")
    pdf.setSubject("Comprovação de posse de certificado profissional")

    pdf.setFillColor(HexColor("#14324a"))
    pdf.rect(0, height - 112, width, 112, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#ffffff"))
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(48, height - 66, "HealthAI")
    pdf.setFont("Helvetica", 11)
    pdf.drawString(48, height - 88, "Verificação automática de cadastro médico")

    y = height - 158
    pdf.setFillColor(HexColor("#17212b"))
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(48, y, "Declaração de titularidade profissional")
    y -= 34
    pdf.setFont("Helvetica", 10.5)
    lines = (
        "Assine digitalmente este PDF com o Certificado Digital do CFM",
        "vinculado ao CRM abaixo. Não edite o documento antes de assinar.",
        "",
        f"Conta HealthAI: {challenge.user_id} — {challenge.account_name}",
        f"Registro declarado: CRM {challenge.crm}/{challenge.crm_uf}",
        f"Emitido em: {_utc_text(challenge.created_at)}",
        f"Válido até: {_utc_text(challenge.expires_at)}",
    )
    for line in lines:
        pdf.drawString(48, y, line)
        y -= 19

    y -= 12
    pdf.setFillColor(HexColor("#e9f2f7"))
    pdf.roundRect(42, y - 76, width - 84, 92, 8, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#14324a"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(56, y - 5, "CÓDIGO DE USO ÚNICO")
    pdf.setFont("Courier-Bold", 10)
    challenge_marker = f"HEALTHAI-CRM-VERIFY:{challenge.challenge_code}"
    pdf.drawString(56, y - 30, challenge_marker)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(
        56,
        y - 54,
        "O código é conferido dentro da parte criptograficamente assinada.",
    )

    y -= 116
    pdf.setFillColor(HexColor("#17212b"))
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawString(48, y, "Como concluir")
    pdf.setFont("Helvetica", 9.5)
    instructions = (
        "1. Abra este arquivo em um assinador compatível com PAdES/ICP-Brasil.",
        "2. Assine usando o certificado emitido pela AR-CFM.",
        "3. Salve o PDF assinado sem fazer outras alterações.",
        "4. Envie o arquivo assinado na página Conta do HealthAI.",
    )
    for line in instructions:
        y -= 18
        pdf.drawString(48, y, line)

    pdf.setFillColor(HexColor("#5a6670"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(
        48,
        48,
        "O HealthAI não armazena o PDF enviado; conserva somente hashes de auditoria.",
    )
    pdf.showPage()
    pdf.save()
    return output.getvalue()


def _configured_trust_source() -> str:
    configured_path = setting("HEALTHAI_ICP_BRASIL_TRUST_ROOTS").strip()
    return configured_path or ICP_BRASIL_TRUST_LIST_URL


def _read_limited_response(response, maximum: int) -> bytes:
    payload = response.read(maximum + 1)
    if len(payload) > maximum:
        raise CrmVerificationUnavailable(
            "A lista de confiança do ITI excedeu o limite permitido."
        )
    return payload


def _certificate_fingerprint(certificate) -> str:
    return hashlib.sha256(certificate.dump()).hexdigest()


@lru_cache(maxsize=4)
def _load_trust_roots(source: str):
    if source != ICP_BRASIL_TRUST_LIST_URL:
        path = Path(source).expanduser()
        try:
            payload = path.read_bytes()
            certificates = tuple(load_certs_from_pemder_data(payload))
        except (OSError, ValueError) as error:
            raise CrmVerificationUnavailable(
                "Não foi possível carregar as raízes ICP-Brasil configuradas."
            ) from error
        if not certificates:
            raise CrmVerificationUnavailable(
                "O arquivo configurado não contém certificados."
            )
        return certificates

    request = Request(
        ICP_BRASIL_TRUST_LIST_URL,
        headers={"User-Agent": "HealthAI/0.1 trust-list-client"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            payload = _read_limited_response(response, TRUST_LIST_MAX_BYTES)
        document = ElementTree.fromstring(payload)
    except (OSError, URLError, ElementTree.ParseError) as error:
        raise CrmVerificationUnavailable(
            "Não foi possível obter a lista de confiança oficial do ITI."
        ) from error

    roots_by_fingerprint = {}
    for element in document.iter():
        if not element.tag.endswith("X509Certificate") or not element.text:
            continue
        try:
            der = base64.b64decode(element.text.strip(), validate=True)
            certificate = next(iter(load_certs_from_pemder_data(der)))
        except (ValueError, StopIteration):
            continue
        fingerprint = _certificate_fingerprint(certificate)
        if fingerprint in OFFICIAL_ROOT_SHA256:
            roots_by_fingerprint[fingerprint] = certificate
    if not roots_by_fingerprint:
        raise CrmVerificationUnavailable(
            "A lista oficial do ITI não contém uma raiz reconhecida."
        )
    return tuple(roots_by_fingerprint.values())


def _flatten_asn1_value(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, bytes):
        try:
            return _flatten_asn1_value(core.load(value).native)
        except (ValueError, TypeError):
            decoded = value.decode("utf-8", errors="ignore").strip()
            return [decoded] if decoded else []
    if isinstance(value, dict):
        flattened: list[str] = []
        for item in value.values():
            flattened.extend(_flatten_asn1_value(item))
        return flattened
    if isinstance(value, (list, tuple, set)):
        flattened = []
        for item in value:
            flattened.extend(_flatten_asn1_value(item))
        return flattened
    text = str(value).strip()
    return [text] if text else []


def _certificate_attribute_values(
    certificate: x509.Certificate,
    oid: str,
) -> set[str]:
    target = ObjectIdentifier(oid)
    values = {
        attribute.value
        for attribute in certificate.subject
        if attribute.oid == target
    }
    for extension in certificate.extensions:
        if extension.oid == target and isinstance(
            extension.value, x509.UnrecognizedExtension
        ):
            values.update(_flatten_asn1_value(extension.value.value))
        if isinstance(extension.value, x509.SubjectAlternativeName):
            for other_name in extension.value.get_values_for_type(x509.OtherName):
                if other_name.type_id == target:
                    values.update(_flatten_asn1_value(other_name.value))
    return {str(value).strip() for value in values if str(value).strip()}


def _canonical_crm(value: str) -> str | None:
    match = re.fullmatch(r"\D*0*(\d{1,10})\D*", value.strip())
    if not match:
        return None
    return str(int(match.group(1)))


def _canonical_state(value: str) -> str | None:
    match = re.fullmatch(r"\W*([A-Za-z]{2})\W*", value.strip())
    return match.group(1).upper() if match else None


def _signed_ranges(embedded_signature) -> tuple[tuple[int, int], ...]:
    try:
        byte_range = [
            int(value)
            for value in embedded_signature.sig_object["/ByteRange"]
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise CrmVerificationError(
            "A assinatura não possui uma faixa criptográfica válida."
        ) from error
    if len(byte_range) < 4 or len(byte_range) % 2:
        raise CrmVerificationError(
            "A assinatura não possui uma faixa criptográfica válida."
        )
    ranges = tuple(
        (byte_range[index], byte_range[index] + byte_range[index + 1])
        for index in range(0, len(byte_range), 2)
    )
    if any(start < 0 or end < start for start, end in ranges):
        raise CrmVerificationError(
            "A assinatura não possui uma faixa criptográfica válida."
        )
    return ranges


def _challenge_is_cryptographically_covered(
    pdf_bytes: bytes,
    challenge_code: str,
    embedded_signature,
) -> bool:
    marker = f"HEALTHAI-CRM-VERIFY:{challenge_code}".encode("ascii")
    ranges = _signed_ranges(embedded_signature)
    offset = pdf_bytes.find(marker)
    while offset >= 0:
        marker_end = offset + len(marker)
        if any(start <= offset and marker_end <= end for start, end in ranges):
            return True
        offset = pdf_bytes.find(marker, offset + 1)
    return False


def validate_signed_challenge(
    pdf_bytes: bytes,
    *,
    challenge_code: str,
    expected_crm: str,
    expected_crm_uf: str,
) -> SignedCrmEvidence:
    """Valida PAdES, confiança ICP-Brasil, desafio e atributos do CFM."""
    if not pdf_bytes.startswith(b"%PDF-"):
        raise CrmVerificationError("Envie um arquivo PDF válido.")
    if len(pdf_bytes) > max_signed_pdf_bytes():
        raise CrmVerificationError("O PDF assinado excede o tamanho permitido.")

    stream = BytesIO(pdf_bytes)
    try:
        reader = PdfFileReader(stream)
        regular_signatures = reader.embedded_regular_signatures
    except Exception as error:
        raise CrmVerificationError(
            "Não foi possível interpretar o PDF enviado."
        ) from error
    if len(regular_signatures) != 1:
        raise CrmVerificationError(
            "O documento deve conter exatamente uma assinatura digital."
        )
    embedded_signature = regular_signatures[0]
    if not _challenge_is_cryptographically_covered(
        pdf_bytes, challenge_code, embedded_signature
    ):
        raise CrmVerificationError(
            "O código do desafio não está protegido pela assinatura digital."
        )

    try:
        context = ValidationContext(
            trust_roots=_load_trust_roots(_configured_trust_source()),
            allow_fetching=True,
            revocation_mode=revocation_mode(),
        )
        signature_status = validate_pdf_signature(
            embedded_signature,
            context,
        )
    except CrmVerificationUnavailable:
        raise
    except Exception as error:
        raise CrmVerificationError(
            "Não foi possível validar a assinatura e sua cadeia de confiança."
        ) from error

    if (
        not signature_status.bottom_line
        or not signature_status.trusted
        or signature_status.coverage is not SignatureCoverageLevel.ENTIRE_FILE
        or signature_status.docmdp_ok is False
    ):
        raise CrmVerificationError(
            "A assinatura é inválida, não confiável ou o PDF foi alterado."
        )

    signer_der = signature_status.signing_cert.dump()
    try:
        signer_certificate = x509.load_der_x509_certificate(signer_der)
    except ValueError as error:
        raise CrmVerificationError(
            "Não foi possível ler o certificado do assinante."
        ) from error

    crm_values = {
        value
        for raw_value in _certificate_attribute_values(
            signer_certificate, CRM_NUMBER_OID
        )
        if (value := _canonical_crm(raw_value))
    }
    state_values = {
        value
        for raw_value in _certificate_attribute_values(
            signer_certificate, CRM_STATE_OID
        )
        if (value := _canonical_state(raw_value))
    }
    if _canonical_crm(expected_crm) not in crm_values:
        raise CrmVerificationError(
            "O certificado não contém o CRM informado na conta."
        )
    if expected_crm_uf.upper() not in state_values:
        raise CrmVerificationError(
            "A UF profissional do certificado não coincide com a conta."
        )

    return SignedCrmEvidence(
        certificate_sha256=hashlib.sha256(signer_der).hexdigest(),
        signed_document_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
    )

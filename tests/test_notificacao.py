"""Testa o e-mail sem enviar nada de verdade (o servidor SMTP é substituído por um falso)."""
import pandas as pd
import pytest

from conciliacao import notificacao


class SMTPFalso:
    enviados = []

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def login(self, usuario, senha):
        self.usuario = usuario

    def send_message(self, msg):
        SMTPFalso.enviados.append(msg)


@pytest.fixture
def resultado():
    return pd.DataFrame([
        {"codigo_venda": "VND-00001", "cliente": "Ana", "valor_venda": 100.0, "valor_pago": 100.0,
         "diferenca": 0.0, "dias_em_aberto": None, "situacao": "Conciliado"},
        {"codigo_venda": "VND-00002", "cliente": "Bruno", "valor_venda": 250.0, "valor_pago": None,
         "diferenca": -250.0, "dias_em_aberto": 12, "situacao": "Venda sem pagamento"},
    ])


def test_html_tem_resumo_e_venda_em_aberto(resultado):
    html = notificacao.montar_html(resultado, pd.DataFrame(), "2026-09-30")
    assert "1 de 2" in html
    assert "VND-00002" in html and "12 dias em aberto" in html
    assert "R$ 250,00" in html


def test_envio_com_anexo(resultado, tmp_path, monkeypatch):
    anexo = tmp_path / "relatorio.xlsx"
    anexo.write_bytes(b"conteudo")
    monkeypatch.setenv("GMAIL_USUARIO", "remetente@gmail.com")
    monkeypatch.setenv("GMAIL_SENHA_APP", "senha-teste")
    monkeypatch.setattr(notificacao.smtplib, "SMTP_SSL", SMTPFalso)

    notificacao.enviar_email("<p>oi</p>", anexo, "Assunto", ["destino@exemplo.com"])

    msg = SMTPFalso.enviados[-1]
    assert msg["To"] == "destino@exemplo.com"
    anexos = [p.get_filename() for p in msg.iter_attachments()]
    assert anexos == ["relatorio.xlsx"]


def test_sem_credenciais_da_erro_claro(tmp_path, monkeypatch):
    monkeypatch.delenv("GMAIL_USUARIO", raising=False)
    monkeypatch.delenv("GMAIL_SENHA_APP", raising=False)
    with pytest.raises(RuntimeError, match="GMAIL_USUARIO"):
        notificacao.enviar_email("<p>oi</p>", tmp_path / "x.xlsx", "Assunto", ["a@b.com"])

import pandas as pd
import os
import time
from binance.client import Client
from binance.enums import *

KEY_BINANCE = "fkcq4FWzNvqFwZEzqiYGYClKf8Rc90GM6xfY3a7x5FeRZRnkZEwqCaABTpyWa8JV"
SECRET_BINANCE = "80LIjgGjpKdtRZXWDqrpEuePWdEMSs7yDMgXbmUAYUbYoYjTWdcNcoBc82NXyuOP"

# Obtendo as chaves de API das variáveis de ambiente
api_key = os.getenv("KEY_BINANCE")
secret_key = os.getenv("SECRET_BINANCE")

if not api_key or not secret_key:
    raise ValueError("As chaves da API Binance não foram definidas.")

# Configurando o cliente da Binance
cliente_binance = Client(api_key, secret_key)

# Configurações gerais
codigo_operado = "DOGEUSDT"
ativo_operado = "DOGE"
periodo_candle = Client.KLINE_INTERVAL_1HOUR
quantidade = 45
delay = 60 


def pegar_lote_info(codigo):
    """
    Obtém informações de LOT_SIZE para garantir que as ordens respeitem os requisitos da Binance.
    """
    try:
        symbol_info = cliente_binance.get_symbol_info(codigo)
        lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
        step_size = float(lot_size_filter['stepSize'])
        min_qty = float(lot_size_filter['minQty'])
        max_qty = float(lot_size_filter['maxQty'])
        return step_size, min_qty, max_qty
    except Exception as e:
        raise ValueError(f"Erro ao obter informações de lote: {e}")


step_size, min_qty, max_qty = pegar_lote_info(codigo_operado)


def ajustar_quantidade(quantidade, step_size, min_qty, max_qty):
    """
    Ajusta a quantidade para respeitar os limites de LOT_SIZE.
    """
    quantidade_ajustada = round(quantidade / step_size) * step_size
    if quantidade_ajustada < min_qty:
        print("Quantidade ajustada é menor que o mínimo permitido.")
        return 0
    if quantidade_ajustada > max_qty:
        print("Quantidade ajustada é maior que o máximo permitido.")
        return max_qty
    return quantidade_ajustada


def pegar_dados(codigo, intervalo):
    """
    Obtém os candles do ativo e retorna um DataFrame processado.
    """
    try:
        candles = cliente_binance.get_klines(symbol=codigo, interval=intervalo, limit=1000)
        precos = pd.DataFrame(candles)
        precos.columns = ["tempo_abertura", "abertura", "maxima", "minima", "fechamento", "volume", "tempo_fechamento",
                          "moedas_negociadas", "numero_trades", "volume_ativo_base_compra", "volume_ativo_cotação", "-"]
        precos = precos[["fechamento", "tempo_fechamento"]]
        precos["fechamento"] = precos["fechamento"].astype(float)
        precos["tempo_fechamento"] = pd.to_datetime(precos["tempo_fechamento"], unit="ms").dt.tz_localize("UTC")
        precos["tempo_fechamento"] = precos["tempo_fechamento"].dt.tz_convert("America/Sao_Paulo")
        precos = precos.sort_values("tempo_fechamento")
        return precos
    except Exception as e:
        print(f"Erro ao obter dados: {e}")
        return pd.DataFrame()


def estrategia_trade(dados, codigo_ativo, ativo_operado, quantidade, posicao):
    """
    Executa a lógica de trading baseada na estratégia de médias móveis.
    """
    dados["media_rapida"] = dados["fechamento"].rolling(window=7, min_periods=1).mean()
    dados["media_devagar"] = dados["fechamento"].rolling(window=40, min_periods=1).mean()

    ultima_media_rapida = dados["media_rapida"].iloc[-1]
    ultima_media_devagar = dados["media_devagar"].iloc[-1]

    print(f"Última Média Rápida: {ultima_media_rapida} | Última Média Devagar: {ultima_media_devagar}")

    try:
        conta = cliente_binance.get_account()
        quantidade_atual = next(float(ativo["free"]) for ativo in conta["balances"] if ativo["asset"] == ativo_operado)
    except Exception as e:
        print(f"Erro ao acessar informações da conta: {e}")
        return posicao

    try:
        if ultima_media_rapida > ultima_media_devagar and not posicao:
            quantidade_ajustada = ajustar_quantidade(quantidade, step_size, min_qty, max_qty)
            if quantidade_ajustada > 0:
                cliente_binance.create_order(
                    symbol=codigo_ativo,
                    side=SIDE_BUY,
                    type=ORDER_TYPE_MARKET,
                    quantity=quantidade_ajustada
                )
                print("COMPROU O ATIVO")
                posicao = True

        elif ultima_media_rapida < ultima_media_devagar and posicao:
            quantidade_venda = ajustar_quantidade(quantidade_atual, step_size, min_qty, max_qty)
            if quantidade_venda > 0:
                cliente_binance.create_order(
                    symbol=codigo_ativo,
                    side=SIDE_SELL,
                    type=ORDER_TYPE_MARKET,
                    quantity=quantidade_venda
                )
                print("VENDEU O ATIVO")
                posicao = False

    except Exception as e:
        print(f"Erro ao executar ordem: {e}")

    return posicao


# Controle de posição inicial
posicao_atual = False

# Loop principal
try:
    while True:
        dados_atualizados = pegar_dados(codigo=codigo_operado, intervalo=periodo_candle)
        if not dados_atualizados.empty:
            posicao_atual = estrategia_trade(
                dados=dados_atualizados,
                codigo_ativo=codigo_operado,
                ativo_operado=ativo_operado,
                quantidade=quantidade,
                posicao=posicao_atual
            )
        time.sleep(delay)
except KeyboardInterrupt:
    print("Execução interrompida pelo usuário.")
except Exception as e:
    print(f"Erro inesperado: {e}")

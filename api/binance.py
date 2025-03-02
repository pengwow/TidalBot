from typing import List, Dict, Any, Optional
from .exchange_base import ExchangeBase


class BinanceAdapter(ExchangeBase):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config["api_key"]
        self.secret_key = config["secret_key"]
        self.base_url = "https://api.binance.com/v3"

    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """获取Binance交易对信息"""
        response = self._request("GET", f"/api/v3/exchangeInfo", params={"symbol": symbol})
        for info in response.get("symbols", []):
            if info["symbol"] == symbol:
                return {
                    "min_quantity": float(info["filters"][0]["minQty"]),
                    "step_size": float(info["filters"][0]["stepSize"]),
                    "contract_size": float(info["contractSize"])
                }
        raise ValueError(f"Symbol {symbol} not found")

    def get_ticker_price(self, symbol: str) -> float:
        """获取Binance最新价格"""
        response = self._request("GET", f"/api/v3/ticker/price", params={"symbol": symbol})
        return float(response["price"])

    def place_order(
            self,
            symbol: str,
            side: str,
            type: str,
            quantity: float,
            price: Optional[float] = None
    ) -> str:
        """在Binance下单"""
        # 转换为最小单位
        symbol_info = self.get_symbol_info(symbol)
        quantity_int = self._normalize_quantity(quantity, symbol_info)

        # 构建参数
        params = {
            "symbol": symbol,
            "side": side,
            "type": type,
            "quantity": quantity_int,
        }
        if type == "limit":
            params["price"] = int(price * 1e-8)  # 假设价格为聪单位

        # 添加签名
        headers = {
            "X-MBX-APIKEY": self.api_key,
            "X-MBX-SIGNATURE": self._generate_signature(params)
        }

        response = self._request("POST", "/api/v3/orders", params=params, headers=headers)
        return response["orderId"]

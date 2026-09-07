"""La destinazione riscritta senza lineette lunghe, che nella prosa italiana non si usano."""
from core import mutate


def run(g):
    mutate.set_meta(g, destination=(
        "La dashboard di Atlas, quella che 'atlas render' scrive su disco e quella che "
        "'atlas serve' tiene viva, e' vestita Grafite, e il suo grafo si naviga esattamente come "
        "il canvas di Nodavia: stessi gesti, stessi archi, stesse animazioni. Resta un file unico "
        "senza risorse remote ne' dipendenze, con i test e l'e2e verdi."))

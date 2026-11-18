from django.urls import path

from inventory.views import (
    CatalogueImportView,
    FefoView,
    LedgerReconcileView,
    MovementListView,
    ProductDeactivateView,
    ProductListCreateView,
    ProductPriceView,
    StockAdjustmentView,
    StockBatchListView,
    StockLocationListCreateView,
    StockReceiptView,
    StockSummaryView,
    StockTransferView,
    SupplierListCreateView,
    ThresholdListCreateView,
)


urlpatterns = [
    path("products/", ProductListCreateView.as_view(), name="inventory-products"),
    path("products/<uuid:pk>/deactivate/", ProductDeactivateView.as_view(), name="inventory-product-deactivate"),
    path("prices/", ProductPriceView.as_view(), name="inventory-price-set"),
    path("catalogue/import/", CatalogueImportView.as_view(), name="inventory-catalogue-import"),
    path("locations/", StockLocationListCreateView.as_view(), name="inventory-locations"),
    path("suppliers/", SupplierListCreateView.as_view(), name="inventory-suppliers"),
    path("receipts/", StockReceiptView.as_view(), name="inventory-receipts"),
    path("stock/", StockSummaryView.as_view(), name="inventory-stock"),
    path("batches/", StockBatchListView.as_view(), name="inventory-batches"),
    path("fefo/", FefoView.as_view(), name="inventory-fefo"),
    path("movements/", MovementListView.as_view(), name="inventory-movements"),
    path("transfers/", StockTransferView.as_view(), name="inventory-transfers"),
    path("adjustments/", StockAdjustmentView.as_view(), name="inventory-adjustments"),
    path("thresholds/", ThresholdListCreateView.as_view(), name="inventory-thresholds"),
    path("reconcile/", LedgerReconcileView.as_view(), name="inventory-reconcile"),
]

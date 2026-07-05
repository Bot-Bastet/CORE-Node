"""Settings window for Bastet CORE-Node."""
import customtkinter as ctk


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Paramètres")
        self.geometry("400x400")
        self.attributes('-topmost', True)

        # Gateway IP
        self.ip_label = ctk.CTkLabel(self, text="Adresse API Gateway (WS):")
        self.ip_label.pack(pady=(20, 5), padx=20, anchor="w")
        self.ip_entry = ctk.CTkEntry(self, width=350)
        self.ip_entry.insert(0, parent.gateway_url)
        self.ip_entry.pack(pady=5, padx=20)

        # API Token
        self.token_label = ctk.CTkLabel(self, text="Token d'authentification:")
        self.token_label.pack(pady=(10, 5), padx=20, anchor="w")
        self.token_entry = ctk.CTkEntry(self, width=350, show="*")
        self.token_entry.insert(0, parent.gateway_token)
        self.token_entry.pack(pady=5, padx=20)

        # Coordonnées (Exemple)
        self.coord_label = ctk.CTkLabel(self, text="Coordonnées / Identifiant du Node:")
        self.coord_label.pack(pady=(10, 5), padx=20, anchor="w")
        self.coord_entry = ctk.CTkEntry(self, width=350)
        self.coord_entry.insert(0, parent.node_coordinates)
        self.coord_entry.pack(pady=5, padx=20)

        # Save Button
        self.save_btn = ctk.CTkButton(self, text="Enregistrer", command=self.save_settings)
        self.save_btn.pack(pady=20)

        self.parent_app = parent

    def save_settings(self):
        self.parent_app.gateway_url = self.ip_entry.get()
        self.parent_app.gateway_token = self.token_entry.get()
        self.parent_app.node_coordinates = self.coord_entry.get()
        self.destroy()

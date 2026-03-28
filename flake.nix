{
  description = "Ghost Mode — OSINT honeypot stack with AI-agent CLI and MCP server";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-darwin" ] (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pkgsLinux = import nixpkgs { system = "x86_64-linux"; };

        ghostmodePython = pkgsLinux.python3.withPackages (ps: with ps; [
          click
          requests
          python-dotenv
          prometheus-client
        ]);

        ghostmodeApp = pkgsLinux.stdenv.mkDerivation {
          pname = "ghostmode";
          version = "0.1.0";
          src = ./.;
          buildInputs = [ ghostmodePython ];
          installPhase = ''
            mkdir -p $out/app $out/bin
            cp -r ghostmode $out/app/ghostmode
            mkdir -p $out/app/docs
            cp -r docs/agent-knowledge $out/app/docs/agent-knowledge 2>/dev/null || true
            cp pyproject.toml $out/app/
            cp AGENTS.md SECURITY.md $out/app/ 2>/dev/null || true

            cat > $out/bin/ghostmode <<WRAPPER
            #!/bin/sh
            export PYTHONPATH="$out/app:\$PYTHONPATH"
            exec ${ghostmodePython}/bin/python -m ghostmode "\$@"
            WRAPPER
            chmod +x $out/bin/ghostmode
          '';
        };

      in {
        packages = {
          ghostmode = ghostmodeApp;

          oci-image = pkgsLinux.dockerTools.buildLayeredImage {
            name = "rg.fr-par.scw.cloud/sanmarcsoft/ghostmode";
            tag = "nix";

            contents = [
              ghostmodeApp
              ghostmodePython
              pkgsLinux.bash
              pkgsLinux.coreutils
              pkgsLinux.curl
              pkgsLinux.jq
              pkgsLinux.cacert
            ];

            config = {
              WorkingDir = "/app";
              Entrypoint = [ "${ghostmodeApp}/bin/ghostmode" ];
              Cmd = [ "serve" ];
              ExposedPorts = {
                "3200/tcp" = {};
              };
              Env = [
                "CHROMADB_HOST=10.0.0.12"
                "CHROMADB_PORT=18000"
                "MCP_PORT=3200"
                "GHOSTMODE_FORMAT=json"
                "SSL_CERT_FILE=${pkgsLinux.cacert}/etc/ssl/certs/ca-bundle.crt"
                "PATH=${ghostmodeApp}/bin:/bin"
                "PYTHONPATH=${ghostmodeApp}/app"
              ];
            };
          };

          default = self.packages.${system}.oci-image;
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            pkgs.python3
            pkgs.python3Packages.click
            pkgs.python3Packages.requests
            pkgs.python3Packages.python-dotenv
            pkgs.python3Packages.pytest
            pkgs.python3Packages.prometheus-client
            pkgs.skopeo
          ];
        };
      }
    );
}

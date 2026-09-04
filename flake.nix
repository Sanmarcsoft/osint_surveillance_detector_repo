{
  description = "Ghost Mode — OSINT honeypot stack with AI-agent CLI and MCP server";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

    # Python runtime closure only (osint #85). nixos-25.05 has NO fastmcp at all,
    # and its chromadb is 0.5.20 against the pinned chromadb-client 1.5.1, so the
    # app's own dependencies cannot be expressed there. Pinned to a revision
    # rather than the nixos-unstable branch so the build stays reproducible:
    # a moving branch would make the image non-deterministic, which is the whole
    # point of building it with Nix. Bump deliberately, never automatically.
    nixpkgs-python.url = "github:NixOS/nixpkgs/3ed67ec0a4d3c7ab4ae1f04f8ee8df07bfa506a2";

    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, nixpkgs-python, flake-utils }:
    flake-utils.lib.eachSystem [ "x86_64-linux" "aarch64-darwin" ] (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pkgsLinux = import nixpkgs { system = "x86_64-linux"; };
        pkgsPython = import nixpkgs-python { system = "x86_64-linux"; };

        # Must cover every third-party module `ghostmode` imports, including the
        # ones imported lazily inside functions. This list was four packages long
        # until osint #85, which is why the Nix image "crashed on startup
        # (essential container exits 1, no logs)" and why production ran a
        # hand-built ECR image for three months instead: `ghostmode serve` raises
        # ImportError on fastmcp before logging is configured, so the traceback
        # never reaches CloudWatch and the failure looks like a silent exit.
        #
        # psycopg2 and starlette are imported inside functions
        # (event_store.py, db_bootstrap.py, mcp_server.py), so omitting them
        # fails at first query rather than at boot, which is worse. Cross-check
        # against pyproject.toml `dependencies` when either list changes;
        # tests/test_nix_runtime_deps.py enforces the correspondence.
        ghostmodePython = pkgsPython.python3.withPackages (ps: with ps; [
          click
          requests
          python-dotenv
          prometheus-client
          fastmcp
          chromadb
          pyjwt
          cryptography
          psycopg2
          starlette
          uvicorn
          boto3
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

          nest-oci-image = pkgsLinux.dockerTools.buildLayeredImage {
            name = "rg.fr-par.scw.cloud/sanmarcsoft/nest-ops";
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
                "NEST_MODE=true"
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

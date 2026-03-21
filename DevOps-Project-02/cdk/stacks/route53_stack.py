from aws_cdk import (
    Stack,
    CfnOutput,
    Duration,
    aws_route53 as route53,
    aws_route53_targets as targets,
    aws_elasticloadbalancingv2 as elbv2,
)
from constructs import Construct


class Route53Stack(Stack):
    """
    Stack — Route53
    Crea:
        - A Record (alias) apuntando al ALB
          app.tudominio.com -> public-alb-xxx.us-east-1.elb.amazonaws.com
    
    Prerequisito:
        - Hosted Zone ya existente en Route53 para tudominio.com
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        alb: elbv2.ApplicationLoadBalancer,
        domain_name: str,        # "tudominio.com"
        subdomain: str,  # "app" → app.tudominio.com
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Importar el Hosted Zone existente ─────────────────────────────────
        # No lo crea — lo busca por nombre de dominio
        hosted_zone = route53.HostedZone.from_lookup(
            self, "HostedZone",
            domain_name=domain_name,
        )

        # ── A Record con alias al ALB ─────────────────────────────────────────
        # ARecord + LoadBalancerTarget es mejor que CnameRecord porque:
        # - Resuelve directamente a IPs, sin segundo lookup
        # - No cobra por queries (los CNAME sí cobran)
        # - Soporta apex domain (tudominio.com sin subdomain)
        self.dns_record = route53.ARecord(
            self, "AlbARecord",
            zone=hosted_zone,
            record_name=subdomain,          # app.tudominio.com
            target=route53.RecordTarget.from_alias(
                targets.LoadBalancerTarget(alb)
            ),
            ttl=Duration.minutes(5),
            comment="Apunta al ALB público del proyecto",
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "AppUrl",
            value=f"https://{subdomain}.{domain_name}",
            description="URL pública de la aplicación",
            export_name="AppUrl",
        )
        CfnOutput(self, "DnsRecordName",
            value=self.dns_record.domain_name,
            description="Nombre del registro DNS creado",
            export_name="DnsRecordName",
        )
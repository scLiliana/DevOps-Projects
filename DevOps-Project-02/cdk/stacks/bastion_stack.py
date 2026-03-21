from aws_cdk import (
    Stack,
    CfnOutput,
    aws_ec2 as ec2,
)
from constructs import Construct


class BastionStack(Stack):
    """
    Stack - Bastion Host
    Crea:
        - EC2 Bastion Host (Subnet Pública BastionVPC, BastionSG, Key Pair)
        - EIP asociada al Bastion Host
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bastion_vpc: ec2.Vpc,
        bastion_sg: ec2.SecurityGroup,
        key_pair_name: str,   # Nombre del Key Pair ya existente en AWS
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── AMI — Amazon Linux 2023 ──────────────────────────────────────────
        ami = ec2.MachineImage.latest_amazon_linux2023(
            cached_in_context=True,
        )

        # ── Key Pair ─────────────────────────────────────────────────────────
        key_pair = ec2.KeyPair.from_key_pair_name(
            self, "DevOpsKeyPair",
            key_pair_name=key_pair_name,
        )

        # ── Bastion Host EC2 ─────────────────────────────────────────────────
        self.bastion = ec2.Instance(
            self, "BastionHost",
            instance_name="BastionHost",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO,
            ),
            machine_image=ami,
            vpc=bastion_vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PUBLIC,
            ),
            security_group=bastion_sg,
            key_pair=key_pair,
            associate_public_ip_address=False,  # Usamos EIP dedicada en su lugar
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(
                        volume_size=8,
                        encrypted=True,
                        delete_on_termination=True,
                    ),
                )
            ],
        )

        # ── EIP + asociación ─────────────────────────────────────────────────
        eip = ec2.CfnEIP(
            self, "BastionEIP",
            domain="vpc",
            tags=[{"key": "Name", "value": "BastionEIP"}],
        )

        ec2.CfnEIPAssociation(
            self, "BastionEIPAssociation",
            instance_id=self.bastion.instance_id,
            allocation_id=eip.attr_allocation_id,
        )

        # ── Outputs ───────────────────────────────────────────────────────────
        CfnOutput(self, "BastionInstanceId",
            value=self.bastion.instance_id,
            description="Bastion Host Instance ID",
            export_name="BastionInstanceId",
        )

        CfnOutput(self, "BastionPublicIP",
            value=eip.ref,
            description="EIP del Bastion Host",
            export_name="BastionPublicIP",
        )
#!/bin/bash

scriptName=$0
var1=$1

# 환경변수 체크
if [ -z "$GITHUB_TOKEN" ] || [ -z "$GITHUB_USER" ]; then
    echo "GITHUB_TOKEN 또는 GITHUB_USER 환경변수가 설정되지 않았습니다."
    exit 1
fi

cd ~/
git config --global user.email "ShellScript"
git config --global user.name "AdminPod"

# 환경변수를 사용한 clone (하드코딩된 토큰 제거)
git clone https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/zongyeng/k-rater-uq-gitops.git

cleanup() {
    cd ~/
    rm -rf ~/k-rater-uq-gitops
}

exit_with_error() {
    cleanup
    exit 1
}

if [ "$var1" = "pm" ]; then
    yq -i '(.spec.generators[0].matrix.generators[0].list.elements[0].env) = "pm"' ~/k-rater-uq-gitops/kustomize/uq-application-set/ApplicationSet.yaml
elif [ "$var1" = "prd" ]; then
    yq -i '(.spec.generators[0].matrix.generators[0].list.elements[0].env) = "prd"' ~/k-rater-uq-gitops/kustomize/uq-application-set/ApplicationSet.yaml
else
    echo "첫번째 인수로 prd 또는 pm을 입력해야 합니다."
    exit_with_error
fi

cd k-rater-uq-gitops

git pull || exit_with_error
if [ "$var1" = "pm" ]; then
    git commit -a -m 'pm 전환'
elif [ "$var1" = "prd" ]; then
    git commit -a -m 'prd 전환'
fi
git push || exit_with_error

# ArgoCD 토큰도 환경변수 사용
curl -X POST -k https://argocd-server.argocd.svc.cluster.local/api/v1/applications/k-rater-uq-application-set/sync \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ARGOCD_AUTH_TOKEN"

cleanup
echo "환경 전환 완료: $var1"
exit 0
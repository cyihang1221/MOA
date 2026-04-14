function isEq=ParamCmp(P1,P2)
%Erik Tengstrand
isEq=1;
N1=fieldnames(P1);
N2=fieldnames(P2);

if numel(N1)==numel(N2)
    R=ones(numel(N1),1);
    for n=1:numel(N1)
        R(n)=min(P1.(N1{n})==P2.(N2{n}));
    end
    isEq=min(R);
end
    
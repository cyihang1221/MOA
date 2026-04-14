function [Scores Peaks PTime Diff]=GFHT_Score(Constant,Coefficients,patterns,Time,samples,TimeShift,Usamp)
%Erik Tengstrand
PTime=Constant+patterns*Coefficients';
Diff=ones(numel(samples),1)*20;
Peaks=zeros(numel(samples),1);

for N=1:numel(Usamp);
    mask=find(samples==Usamp(N));
    [Val index]=min(abs(Time(mask)-PTime(Usamp(N))));
    Diff(mask(index))=Val;
    Peaks(mask(index))=1;
end

Scores=exp(-Diff.^2/(TimeShift.^2)); 


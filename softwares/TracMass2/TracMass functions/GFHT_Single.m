function [hID, Expected, SelectedPatterns, SelectedPatternTimes, ExplainedVar] = GFHT_Single(peakList, parameters, ID, nSamp)
%Erik Tengstrand
Components=parameters.Components;
Resolution=3;
Penalty=parameters.Penalty;
TimeShift=parameters.TimeTolerance/60;
MinPeaks=1;
Opt=optimset('MaxIter',300,'Display','on','MaxFunEvals',1000);
Expected.Time=[];
Expected.ID=[];
NextGid=max(peakList.gid)+1;

[patterns PatternTimes]=GFHT_patterns(peakList);

%Creating sets of coefficients to fit GFHT
Points=Resolution^Components;
Coefficients=zeros(Points,Components);
Grid=-1.5:(3/(Resolution-1)):1.5;
for N=1:Components
    Coefficients(:,N)=repmat(sort(repmat(Grid',Resolution^(N-1),1)),Points/(Resolution^N),1);
end


mask=peakList.gid == ID;
time=peakList.time(mask);
samples=peakList.sample(mask);
hID=zeros(size(samples));
AllPeaks=1:numel(time);

[~, index]=sort(abs(PatternTimes-mean(time)));
SelectedPatterns=patterns(:,index(1:20));
SelectedPatternTimes=PatternTimes(index(1:20));
[U,s,~] = svd(mean_center(SelectedPatterns));
PCAPatterns=U(:,1:Components)*s(1:Components,1:Components);
Constant=mean(time)+std(time)*Grid;

ExplainedVar=diag(s)/sum(s(:))*100;
SelectedPeaks=[1 1 1];

%test until no more peaks can be grouped
while numel(SelectedPeaks)>=MinPeaks
    uSamp=unique(samples);
    Score=zeros(Points,Resolution);
    for P=1:Resolution
        for Q=1:Points;
            ScoreVector=GFHT_Score(Constant(P),Coefficients(Q,:),PCAPatterns,time,samples,TimeShift,uSamp);
            Score(Q,P)=sum(ScoreVector);
        end
    end
    [MaxScores, C1]=max(Score);
    [~,C2]=max(MaxScores);
    StartCoeffs(1)=Constant(C2);
    StartCoeffs(2:(Components+1))=Coefficients(C1(C2),:);
    
    %optimise the coefficients
    fcn=@(Coeffs)GFHT_Min(Coeffs(1),Coeffs(2:end),PCAPatterns,time,samples,TimeShift,nSamp,uSamp,Penalty);
    FinalCoeffs=fminsearch(fcn,StartCoeffs,Opt);
    [~, Peaks, PTime, Diff]=GFHT_Score(FinalCoeffs(1),FinalCoeffs(2:end),PCAPatterns,time,samples,TimeShift,uSamp);
    SelectedPeaks=find(Peaks.*(Diff<TimeShift));
    if numel(SelectedPeaks)==0
        break
    end
    
    %store the expected times and remove the peaks from further testing
    hID(AllPeaks(SelectedPeaks))=NextGid;
    Expected.Time((end+1):(end+numel(PTime)))=PTime;
    Expected.ID((end+1):(end+numel(PTime)))=NextGid;
    NextGid=NextGid+1;
    time(SelectedPeaks)=[];
    samples(SelectedPeaks)=[];
    AllPeaks(SelectedPeaks)=[];
end
